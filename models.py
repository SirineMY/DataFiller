
from sklearn.discriminant_analysis import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
import pandas as pd
from sklearn.model_selection import train_test_split
import numpy as np




class KNNCustomImputer:
    def __init__(self, n_neighbors=20):
        self.n_neighbors = n_neighbors
        self.neighbors = NearestNeighbors(n_neighbors=n_neighbors)
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy='mean')
    
    def fit(self, X):
        # Vérification si X est un DataFrame pour gérer les noms de caractéristiques
        if isinstance(X, pd.DataFrame):
            self.feature_names_ = X.columns.tolist()
        else:
            self.feature_names_ = None
        
        # Imputation et mise à l'échelle pour l'ajustement
        X_imputed = self.imputer.fit_transform(X)
        X_scaled = self.scaler.fit_transform(X_imputed)
        self.neighbors.fit(X_scaled)
        
        # Stockage des données d'entraînement imputées et mises à l'échelle pour l'utilisation dans transform
        self.X_train_imputed_scaled_ = X_scaled
        return self
    
    def transform(self, X):
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        X_missing = np.isnan(X)
        X_temp_imputed = self.imputer.transform(X)  # Utiliser les statistiques d'imputation apprises lors du fit
        X_scaled = self.scaler.transform(X_temp_imputed)  # Utiliser les statistiques de mise à l'échelle apprises lors du fit
        
        for i in range(X_scaled.shape[0]):
            missing_features = np.where(X_missing[i])[0]
            if missing_features.size > 0:
                distances, neighbors_indices = self.neighbors.kneighbors([X_scaled[i]])
                for feature_index in missing_features:
                    # Utiliser les données d'entraînement imputées et mises à l'échelle pour trouver les valeurs des voisins
                    neighbor_values = self.X_train_imputed_scaled_[neighbors_indices[0], feature_index]
                    X_temp_imputed[i, feature_index] = np.mean(neighbor_values)
        
        # Retourner les données imputées dans le format original
        if self.feature_names_:
            return pd.DataFrame(X_temp_imputed, columns=self.feature_names_)
        return X_temp_imputed

    def fit_transform(self, X):
        return self.fit(X).transform(X)

