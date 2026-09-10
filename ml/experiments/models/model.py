import os
import kagglehub
import pandas as pd
path = kagglehub.dataset_download("hubertsidorowicz/steam-games-dataset-daily-updates")
csv_file_path = os.path.join(path, "steam_games.csv")
df = pd.read_csv(csv_file_path)
print(df.head())
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
df['total_reviews'] = df['positive'].fillna(0) + df['negative'].fillna(0)
df['review_ratio'] = np.where(df['total_reviews'] > 0, df['positive'] / df['total_reviews'], 0.5)
df['success_score'] = (df['review_ratio'] * 50) + np.clip(np.log1p(df['peak_ccu'].fillna(0)) * 5, 0, 50)

df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
df['release_month'] = df['release_date'].dt.month.fillna(1).astype(int)
df['release_dayofweek'] = df['release_date'].dt.dayofweek.fillna(0).astype(int)

df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(14.99)
df['dlc_count'] = df['dlc_count'].fillna(0).astype(int)
df['achievements'] = df['achievements'].fillna(0).astype(int)

df['windows'] = df['windows'].fillna(True).astype(int)
df['mac'] = df['mac'].fillna(False).astype(int)
df['linux'] = df['linux'].fillna(False).astype(int)

df['primary_genre'] = df['genres'].fillna('Indie').apply(lambda x: str(x).split(',')[0].strip())
df['genre_code'] = df['primary_genre'].astype('category').cat.codes


genre_categories = dict(enumerate(df['primary_genre'].astype('category').cat.categories))
joblib.dump(genre_categories, "genre_mapping.pkl")

feature_cols = [
    'genre_code', 'price', 'release_month', 'release_dayofweek', 
    'dlc_count', 'achievements', 'windows', 'mac', 'linux'
]

X = df[feature_cols]
y = df['success_score']


X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)


joblib.dump(model, "steam_success_model.pkl")
print(f"Model successfully trained! R2 Score: {model.score(X_test, y_test):.3f}")