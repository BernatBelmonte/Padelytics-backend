import sys
import os
import pandas as pd
import pickle

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ML_MODELS,
    EXPECTED_FEATURES
)

class ModelPredictor:
    def __init__(self, model_name):
        self.model = self._load_model(model_name)

    def _load_model(self, model_name):
        model = os.path.join(ML_MODELS, model_name)
        with open(model, 'rb') as f:
            model = pickle.load(f)
        return model
    
    def predict(self, match_data):
        input_df = match_data[EXPECTED_FEATURES]
    
        # returns [prob_loss, prob_win] -> we want [1] for Team 1 Win probability
        probability = self.model.predict_proba(input_df)[0][1]
        
        return probability
