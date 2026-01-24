import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    API_DATA_FILE,
    MODEL_DATA_FILE,
    EXP_DYNAMIC_PAIRS_FILE,
    EXP_DYNAMIC_PLAYERS_FILE,
    EXP_MATCHES_FILE,
    EXP_STATIC_PLAYERS_FILE,
    EXP_TOURNAMENTS_FILE,
)

class APIDataPreparator:
    def __init__(self):
        self.dynamic_pairs = pd.read_csv(EXP_DYNAMIC_PAIRS_FILE)
        self.dynamic_players = pd.read_csv(EXP_DYNAMIC_PLAYERS_FILE)
        self.matches = pd.read_csv(EXP_MATCHES_FILE)
        self.static_players = pd.read_csv(EXP_STATIC_PLAYERS_FILE)
        self.tournaments = pd.read_csv(EXP_TOURNAMENTS_FILE)

    def start(self):
        print(" Data Preparator for API and Model ")
        print("==================================")
        df_api = self._prepare_data_for_api()
        self._prepare_data_for_model(df_api)
        print("✅ Data preparation completed.")

    def _prepare_data_for_api(self):
        cols_to_merge = ['player_id','player_code','country','height','position','birth_date']
        print(self.static_players.info())
        print(self.dynamic_pairs.info())
        # Player 1 stats merge
        df1 = self.dynamic_pairs.merge(
            self.static_players[cols_to_merge].rename(columns={
                'height': 'p1_height', 
                'position': 'p1_position',
                'name': 'p1_name',
                'slug': 'p1_slug',
                'country': 'p1_country',
                'birth_date': 'p1_birth_date'
            }),
            left_on=['p1_id', 'p1_code'],
            right_on=['player_id', 'player_code'],
            how='left'
        )

        # Player 2 stats merge
        df1 = df1.merge(
            self.static_players[cols_to_merge].rename(columns={
                'height': 'p2_height', 
                'position': 'p2_position',
                'name': 'p2_name',
                'slug': 'p2_slug',
                'country': 'p2_country',
                'birth_date': 'p2_birth_date'
            }),
            left_on=['p2_id', 'p2_code'],
            right_on=['player_id', 'player_code'],
            how='left'
        )
        print(df1.info())
        df1.drop(columns=[
            'pair_code', 'pair_id', 
            'p1_code', 'p1_name', 'p1_slug',
            'p2_code', 'p2_name', 'p2_slug',
            'p1_id', 'p2_id', 'player_id_x',
            'player_code_x', 'player_id_y', 'player_code_y',    
            'points_behind_leader', 
            'is_number_one', 
            'is_new_pair', ], inplace=True)
        
        df2 = self.matches.merge(
            self.tournaments,
            left_on='tournament_id',
            right_on='tournaments_id',
            how='left'
        )
        df2.drop(columns=[
            'matchId', 'club', 'slug', 'fip_source_url',
            'year', 'status', 'start_date_utc', 
            'end_date_utc', 'prize_money', 'country_code', 
            'event_code', 'tournaments_id'], inplace=True)
        
        df2['date'] = pd.to_datetime(df2['date'])
        df1['snapshot_date'] = pd.to_datetime(df1['snapshot_date'])

        df2 = df2.sort_values('date')
        df1 = df1.sort_values('snapshot_date')

        # Team 1 stats merge
        df_final = pd.merge_asof(
            df2,
            df1.add_suffix('_t1'),
            left_on='date',
            right_on='snapshot_date_t1',
            left_by='team1_slug',
            right_by='pair_slug_t1',
            direction='backward' # Only look at past stats, not future ones
        )

        # Team 2 stats merge
        df_final = pd.merge_asof(
            df_final,
            df1.add_suffix('_t2'),
            left_on='date',
            right_on='snapshot_date_t2',
            left_by='team2_slug',
            right_by='pair_slug_t2',
            direction='backward'
        )

        df_final.drop(columns=[
            'pair_slug_t1', 'snapshot_date_t1',
            'pair_slug_t2', 'snapshot_date_t2'
            ], inplace=True, errors='ignore')

        
        direct_diff_cols = [
            'total_points', 'points_change', 'partnership_time_days',
            'tournaments_played_together', 
            'matches_last_14_days', 'average_round_value',
            'finals_conversion_rate', 'season_win_pct', 'dominance_ratio', 
            'straight_sets_win_rate', 'avg_games_conceded_per_set', 
            'tie_break_win_pct', 'closing_efficiency', 'comeback_rate'
        ]

        # Calculate differences for selected stats
        for col in direct_diff_cols:
            if col == 'total_points':
                df_final[f'diff_log_{col}'] = np.log1p(df_final[f'{col}_t1'].astype(float)) - np.log1p(df_final[f'{col}_t2'].astype(float))
            else:
                df_final[f'diff_{col}'] = df_final[f'{col}_t1'].astype(float) - df_final[f'{col}_t2'].astype(float)

        df_final['match_quality_sum'] = np.log1p(df_final['total_points_t1']) + np.log1p(df_final['total_points_t2'])

        p1_height_t1, p2_height_t1 = df_final['p1_height_t1'], df_final['p2_height_t1']
        p1_height_t2, p2_height_t2 = df_final['p1_height_t2'], df_final['p2_height_t2']
        if p1_height_t1 is not None and p2_height_t1 is not None and p1_height_t2 is not None and p2_height_t2 is not None:
            df_final['avg_height_t1'] = (df_final['p1_height_t1'] + df_final['p2_height_t1']) / 2
            df_final['avg_height_t2'] = (df_final['p1_height_t2'] + df_final['p2_height_t2']) / 2
            df_final['diff_avg_height'] = df_final['avg_height_t1'] - df_final['avg_height_t2']
        else:
            df_final['diff_avg_height'] = None

        df_final['target_team1_wins'] = (df_final['winner_team'] == 1).astype(int)

        df_final.drop(columns=[
            'winner_team',
        ], inplace=True, errors='ignore')

        print("Final shape:", df_final.shape)
        print(df_final.info())
        self._save_data(df_final, type='api')
        return df_final
    
    def _prepare_data_for_model(self, df_model):
        keep_cols = [
            'tournaments_match_id', 'date', 'match_quality_sum',
            'court_speed_index', 'team1_slug', 'team2_slug',
            'target_team1_wins',
        ] + [col for col in df_model.columns if col.startswith('diff_')]
        df_model = df_model[keep_cols].copy()

        df_model.drop(columns=[
            'diff_partnership_time_days',
            'diff_closing_efficiency',
            'diff_dominance_ratio',
            'diff_average_round_value',
            'diff_straight_sets_win_rate',
        ], inplace=True)

        df_model = self._prepare_symmetric_data(df_model)

        print("Model Data shape:", df_model.shape)
        print(df_model.info())
        self._save_data(df_model, type='model')
        return df_model

    def _prepare_symmetric_data(self, df):
        df_flipped = df.copy()
        
        # Invert the target (If T1 won, now T2 wins)
        df_flipped['target_team1_wins'] = 1 - df_flipped['target_team1_wins']
        
        # Invert ONLY the difference columns
        diff_cols = [c for c in df.columns if c.startswith('diff_')]
        df_flipped[diff_cols] = df_flipped[diff_cols] * -1
        df_flipped['team1_slug'], df_flipped['team2_slug'] = df_flipped['team2_slug'], df_flipped['team1_slug']
        # Combine and Sort by Date
        df_sym = pd.concat([df, df_flipped], ignore_index=True)
        df_sym['date'] = pd.to_datetime(df_sym['date'])
        df_sym = df_sym.sort_values('date').reset_index(drop=True)
        return df_sym
    
    def _save_data(self, df, type):
        if type == 'api':
            df.to_csv(API_DATA_FILE, index=False)
            print(f"API data saved to {API_DATA_FILE}") 
        elif type == 'model':
            df.to_csv(MODEL_DATA_FILE, index=False)
            print(f"Model data saved to {MODEL_DATA_FILE}")

if __name__ == "__main__":
    preparator = APIDataPreparator()
    preparator.start()