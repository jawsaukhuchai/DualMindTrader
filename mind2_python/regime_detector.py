import joblib
import logging
import numpy as np
from typing import Dict, Any

logger = logging.getLogger("RegimeDetector")

REGIME_CLASSES = ["trend", "range", "high_vol", "low_vol"]

class RegimeDetector:
    """
    AI-based Regime Detector
    - ML model: RandomForest / XGBoost / LSTM (exported as joblib)
    - Input: indicator snapshot (dict from Mind1 JSON)
    - Output: regime class + probability
    """
    def __init__(self, model_path: str = None):
        self.model = None
        self.model_path = model_path
        if model_path:
            try:
                self.model = joblib.load(model_path)
                self.classes_ = list(getattr(self.model, "classes_", REGIME_CLASSES))
                logger.info(f"[RegimeDetector] Loaded model {model_path}")
            except Exception as e:
                logger.error(f"[RegimeDetector] Load fail: {e}")
                self.model = None
                self.classes_ = REGIME_CLASSES
        else:
            self.classes_ = REGIME_CLASSES

    def _featurize(self, entry: Dict[str, Any]) -> np.ndarray:
        """
        แปลง indicators เป็น feature vector
        Mind1 JSON -> dict เช่น {"ema":..,"rsi":..,"atr":..,"adx":..,"vol_profile":..}
        """
        feats = [
            entry.get("ema_slope", 0.0),
            entry.get("rsi", 50.0),
            entry.get("atr", 1.0),
            entry.get("atr_ma", 1.0),
            entry.get("adx", 20.0),
            entry.get("bb_width", 0.0),
            entry.get("volume_profile_imb", 0.0),
        ]
        return np.array(feats, dtype=float).reshape(1, -1)

    def predict(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        คืน regime + proba
        ถ้า model ไม่มี → fallback rule-based
        """
        if self.model:
            try:
                X = self._featurize(entry)
                if hasattr(self.model, "predict_proba"):
                    proba = self.model.predict_proba(X)[0]
                    idx = int(np.argmax(proba))
                    regime = self.classes_[idx]
                    return {"regime": regime, "proba": float(proba[idx]), "raw": dict(zip(self.classes_, proba))}
                else:
                    pred = self.model.predict(X)[0]
                    return {"regime": str(pred), "proba": 0.5, "raw": {}}
            except Exception as e:
                logger.error(f"[RegimeDetector] predict fail: {e}")

        # --- fallback rule-based ---
        atr, atr_ma = entry.get("atr", 1.0), entry.get("atr_ma", 1.0)
        adx = entry.get("adx", 20.0)

        if adx > 25 and atr > atr_ma:
            return {"regime": "trend", "proba": 0.6, "raw": {}}
        elif adx < 20 and atr < atr_ma:
            return {"regime": "range", "proba": 0.6, "raw": {}}
        elif atr > 1.5 * atr_ma:
            return {"regime": "high_vol", "proba": 0.6, "raw": {}}
        else:
            return {"regime": "low_vol", "proba": 0.6, "raw": {}}
