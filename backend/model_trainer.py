import sys
import os
import pandas as pd
import numpy as np
import pickle

from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import f1_score, log_loss, roc_auc_score, accuracy_score
from sklearn.ensemble import VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from xgboost import XGBClassifier

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MODEL_DATA_FILE,
    ML_MODELS
)

class ModelTrainer:
   
    def __init__(self):
        self.model_data = pd.read_csv(MODEL_DATA_FILE)
        self.X_train, self.y_train, self.X_test, self.y_test, self.meta_test = self._prepare_data()
        self.models = {}
        self.results = pd.DataFrame(columns=['accuracy', 'f1_macro', 'log_loss', 'auc_roc'])
    
    def _prepare_data(self):
        
        SPLIT_DATE = '2025-10-01' 
        START_DATE = '2024-05-01'

        # Last nan checks
        self.model_data = self.model_data.dropna()

        train_mask = (self.model_data['date'] < SPLIT_DATE) & (self.model_data['date'] > START_DATE)
        test_mask = self.model_data['date'] >= SPLIT_DATE
        # Exclude ids and slugs for training
        feature_cols = [c for c in self.model_data.columns if c.startswith('diff_') or c == 'court_speed_index' or c == 'match_quality_sum']
        target_col = 'target_team1_wins'

        X_train = self.model_data.loc[train_mask, feature_cols]
        y_train = self.model_data.loc[train_mask, target_col]

        X_test = self.model_data.loc[test_mask, feature_cols]
        y_test = self.model_data.loc[test_mask, target_col]

        # Save Meta-Data for analysis: ids, slugs
        meta_test = self.model_data.loc[test_mask, ['tournaments_match_id', 'date', 'target_team1_wins', 'team1_slug', 'team2_slug',]].copy()

        print(f"Total Samples: {len(self.model_data)}")
        print(f"Train Set: {len(X_train)} rows")
        print(f"Test Set:  {len(X_test)} rows")
        print(f"Features: {len(feature_cols)}")
        print(self.model_data.info())

        return X_train, y_train, X_test, y_test, meta_test
    
    def _confusion(self, true, pred):
        pred = pd.Series(pred)
        true = pd.Series(true)
        
        true.name = 'target'
        pred.name = 'predicted'
        cm = pd.crosstab(true.reset_index(drop=True), pred.reset_index(drop=True))
        cm = cm[cm.index]
        return cm

    def _compute_metrics(self, y_true,y_pred, y_proba=None):
        f1_macro = f1_score(y_true, y_pred, average='macro')
        accuracy = accuracy_score(y_true, y_pred)
        # Secondary metrics (only if probabilities provided)
        if y_proba is not None:
            # Ensure probabilities are 1D (probability of class 1)
            if y_proba.ndim > 1:
                y_proba = y_proba[:, 1]

            logloss = log_loss(y_true, y_proba)
            auc = roc_auc_score(y_true, y_proba)
        else:
            logloss = None
            auc = None

        return {
            "accuracy": accuracy,
            "f1_macro": f1_macro,
            "log_loss": logloss,
            "auc_roc": auc
        }
    
    def _train(self):
        pipe_LogReg_Normal = Pipeline([ ('scaler', StandardScaler()), ('model', LogisticRegression()) ])

        model_LogisticRegression = pipe_LogReg_Normal.fit(self.X_train, self.y_train)

        y_pred = model_LogisticRegression.predict(self.X_test)
        y_proba = model_LogisticRegression.predict_proba(self.X_test)[:, 1]

        self.results.loc['LogReg', :] = self._compute_metrics(self.y_test, y_pred, y_proba) # type: ignore
        self.models['LogReg'] = model_LogisticRegression

        pipe_LogReg_Tuned = Pipeline([
            ('scaler', StandardScaler()),
            ('model', LogisticRegression())
        ])

        param_grid = {
            'model__C': [
                0.0001, 0.0003, 0.001, 0.003,
                0.01, 0.03, 0.1, 0.3,
                1, 3, 10, 30, 100
            ],
            'model__penalty': [
                'l1', 'l2', 'elasticnet', 'none'
            ],
            'model__solver': [
                'liblinear',     # supports l1, l2
                'lbfgs',         # supports l2, none
                'saga',          # supports l1, l2, elasticnet
                'newton-cg'      # supports l2, none
            ],
            'model__l1_ratio': [
                0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0
            ],
            'model__max_iter': [
                200, 500, 1000, 2000
            ],
            'model__tol': [
                1e-4, 1e-5, 1e-6
            ]
        }

        search = RandomizedSearchCV(
            pipe_LogReg_Tuned,
            param_distributions=param_grid,
            cv=TimeSeriesSplit(n_splits=4),
            scoring='neg_log_loss',
            n_iter=10,
            n_jobs=-1,
            error_score=np.nan
        )

        model_LogisticRegression_Tuned = search.fit(self.X_train, self.y_train)

        y_pred = model_LogisticRegression_Tuned.predict(self.X_test)
        y_proba = model_LogisticRegression_Tuned.predict_proba(self.X_test)[:, 1]

        self.results.loc['LogRegTuned', :] = self._compute_metrics(self.y_test, y_pred, y_proba) # type: ignore
        self.models['LogRegTuned'] = model_LogisticRegression_Tuned

        model_XGBoost = XGBClassifier().fit(self.X_train, self.y_train)

        y_pred = model_XGBoost.predict(self.X_test)
        y_proba = model_XGBoost.predict_proba(self.X_test)[:, 1]

        self.results.loc['XGBoost', :] = self._compute_metrics(self.y_test, y_pred, y_proba) # type: ignore
        self.models['XGBoost'] = model_XGBoost

        param_grid_xgb = {
            'n_estimators': [200, 400, 600, 800, 1000],
            'learning_rate': [0.005, 0.01, 0.02, 0.05, 0.1],
            'max_depth': [2, 3, 4, 5, 6],
            'min_child_weight': [1, 3, 5, 7, 10],
            'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
            'gamma': [0, 0.1, 0.2, 0.3, 1],
            'reg_alpha': [0, 0.001, 0.01, 0.1, 1],
            'reg_lambda': [0, 0.1, 1, 5],
        }

        tscv = TimeSeriesSplit(n_splits=4)

        xgb_base = XGBClassifier(
            eval_metric='mlogloss',
        )

        search_xgb = RandomizedSearchCV(
            estimator=xgb_base,
            param_distributions=param_grid_xgb,
            n_iter=40,
            scoring='neg_log_loss',
            cv=tscv,
            n_jobs=-1,
            verbose=1
        )

        model_XGBoost_Tuned = search_xgb.fit(self.X_train, self.y_train)

        y_pred = model_XGBoost_Tuned.predict(self.X_test)
        y_proba = model_XGBoost_Tuned.predict_proba(self.X_test)[:, 1]

        self.results.loc['XGBoost_Tuned', :] = self._compute_metrics(self.y_test, y_pred, y_proba) # type: ignore
        self.models['XGBoost_Tuned'] = model_XGBoost_Tuned

        model_VotingSoft = VotingClassifier([('LogRegTuned', model_LogisticRegression_Tuned), ('XGBoost_Tuned', model_XGBoost_Tuned)], voting='soft')
        model_VotingSoft.fit(self.X_train, self.y_train)

        y_pred = model_VotingSoft.predict(self.X_test)
        y_proba = model_VotingSoft.predict_proba(self.X_test)[:, 1]

        self.results.loc['VotingSoft', :] = self._compute_metrics(self.y_test, y_pred, y_proba) # type: ignore
        self.models['VotingSoft'] = model_VotingSoft


    def _evaluate_and_deploy(self):
        print("Model Evaluation Results:")
        print(self.results)
        print("Deploying Soft Voting Classifier as final model.")
        final_model = self.models['VotingSoft']
        file = os.path.join(ML_MODELS, 'voting_soft_model.pkl') # Change depending on final choice
        try:
            with open(file, 'wb') as f:
                pickle.dump(final_model, f)
            print(f"Model saved to {file}")
        except Exception as e:
            print(f"Error saving model: {e}")

    def train_and_evaluate(self):
        print(" Model Trainer and Evaluator ")
        print("============================")
        self._train()
        self._evaluate_and_deploy()

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.train_and_evaluate()