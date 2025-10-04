from typing import Dict, Any, Optional

import logging
import joblib
import numpy as np

# -----------------------------
# Logger setup
# -----------------------------
logger = logging.getLogger("Integrate")
logger.setLevel(logging.DEBUG)       # ✅ force debug level
logger.propagate = True              # ✅ let logs bubble up
if not logger.handlers:              # ✅ ensure handler exists
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


# ================= Regime-based weights =================
REGIME_STRATEGY_WEIGHTS = {
    "trend":   {"scalp": 0.8, "day": 1.0, "swing": 1.2},
    "range":   {"scalp": 1.2, "day": 0.8, "swing": 0.5},
    "high_vol": {"scalp": 1.5, "day": 1.0, "swing": 0.7},
    "low_vol": {"scalp": 0.5, "day": 1.0, "swing": 1.0},
    "normal":  {"scalp": 1.0, "day": 1.0, "swing": 1.0},
}


def dynamic_threshold(base_th: float, atr: float, atr_ma: float) -> float:
    if atr_ma <= 0:
        return base_th
    ratio = atr / atr_ma
    adj = min(max(1 / ratio, 0.8), 1.2)
    return base_th * adj


def _fallback_dict(
    scalp_res: Dict[str, Any],
    day_res: Dict[str, Any],
    swing_res: Dict[str, Any],
    mode: str,
    weights: Dict[str, float],
    regime: str,
    threshold: float,
) -> Dict[str, Any]:
    """Standardized fallback response."""
    return {
        "decision": "HOLD",
        "confidence": 0.0,
        "scalp": scalp_res,
        "day": day_res,
        "swing": swing_res,
        "mode": mode,
        "weights": weights,
        "score": 0.0,
        "num_entries": 0,
        "threshold": threshold,
        "regime": regime,
    }


def integrate_decisions(
    scalp_res: Dict[str, Any] = None,
    day_res: Dict[str, Any] = None,
    swing_res: Dict[str, Any] = None,
    sym_cfg: Dict[str, Any] = None,
    global_cfg: Dict[str, Any] = None,
    regime: str = "normal",
    mode: str = None,
    weights: Dict[str, float] = None,
) -> Optional[Dict[str, Any]]:
    """Hybrid integration (Strength Hybrid score-based)."""

    # fallback args
    scalp_res = scalp_res or {"decision": "HOLD", "confidence": 0.0}
    day_res   = day_res   or {"decision": "HOLD", "confidence": 0.0}
    swing_res = swing_res or {"decision": "HOLD", "confidence": 0.0}

    # default weights
    weights_final = {"scalp": 0.33, "day": 0.33, "swing": 0.34}
    if global_cfg and "weights" in global_cfg:
        weights_final.update(global_cfg["weights"])
    if sym_cfg and "weights" in sym_cfg:
        weights_final.update(sym_cfg["weights"])
    if weights:
        weights_final.update(weights)

    # regime overlay
    regime_w = REGIME_STRATEGY_WEIGHTS.get(regime, REGIME_STRATEGY_WEIGHTS["normal"])
    weights_final = {k: weights_final[k] * regime_w.get(k, 1.0) for k in weights_final}

    # decision → score
    def score(decision: str) -> int:
        if decision == "BUY":
            return 1
        elif decision == "SELL":
            return -1
        elif decision in ("HOLD", None):
            return 0
        else:
            logger.warning(f"[Hybrid] unknown decision value={decision}, fallback=HOLD")
            return None  # trigger fallback

    scalp_score = score(scalp_res.get("decision"))
    day_score   = score(day_res.get("decision"))
    swing_score = score(swing_res.get("decision"))

    if None in (scalp_score, day_score, swing_score):
        return _fallback_dict(scalp_res, day_res, swing_res, "HOLD", weights_final, regime, 0.05)

    total_score = scalp_score + day_score + swing_score

    base_th = global_cfg.get("decision_threshold", 0.05) if global_cfg else 0.05
    atr_val = sym_cfg.get("last_atr", 1.0) if sym_cfg else 1.0
    atr_ma  = sym_cfg.get("atr_ma", atr_val) if sym_cfg else atr_val
    threshold = dynamic_threshold(base_th, atr_val, atr_ma)

    if total_score > threshold:
        decision = "BUY"
    elif total_score < -threshold:
        decision = "SELL"
    else:
        decision = "HOLD"

    confs = [
        scalp_res.get("confidence", 0.0) * weights_final["scalp"],
        day_res.get("confidence", 0.0) * weights_final["day"],
        swing_res.get("confidence", 0.0) * weights_final["swing"],
    ]
    avg_conf = sum(confs) / sum(weights_final.values()) if sum(weights_final.values()) > 0 else 0.0

    mode = mode or (sym_cfg.get("integration_mode") if sym_cfg else None) or "hybrid"

    if mode == "strict":
        num_entries = 1

    elif mode == "majority":
        num_entries = 2
        if avg_conf >= 1.0:
            if scalp_res.get("decision") == day_res.get("decision") == swing_res.get("decision"):
                num_entries = 3

    elif mode == "priority":
        num_entries = sym_cfg.get("max_num_entries", 3) if sym_cfg else 3
        priority_dec = sym_cfg.get("priority_decision") if sym_cfg else None
        if priority_dec and priority_dec in (
            scalp_res.get("decision"),
            day_res.get("decision"),
            swing_res.get("decision"),
        ):
            decision = priority_dec
        else:
            # ✅ dual behavior: fallback HOLD only if explicitly requested
            if sym_cfg and sym_cfg.get("priority_fallback", False):
                logger.warning("[Hybrid] priority mode but no match → fallback HOLD")
                return _fallback_dict(scalp_res, day_res, swing_res, "HOLD", weights_final, regime, threshold)
            # otherwise → keep score-based decision (BUY/SELL/HOLD)

    elif mode == "hybrid":
        if avg_conf > 0.7:
            num_entries = 3
        elif avg_conf > 0.5:
            num_entries = 2
        else:
            num_entries = 1

    else:
        logger.warning(f"[Hybrid] unknown mode={mode}, fallback=HOLD")
        return _fallback_dict(scalp_res, day_res, swing_res, "HOLD", weights_final, regime, threshold)

    # enforce max_num_entries from config if provided
    if sym_cfg and "max_num_entries" in sym_cfg:
        num_entries = min(num_entries, sym_cfg["max_num_entries"])

    logger.debug(
        f"[Hybrid] regime={regime}, scalp={scalp_res.get('decision')}({scalp_res.get('confidence',0):.2f}), "
        f"day={day_res.get('decision')}({day_res.get('confidence',0):.2f}), "
        f"swing={swing_res.get('decision')}({swing_res.get('confidence',0):.2f}) "
        f"-> score={total_score:.2f}, th={threshold:.2f}, conf={avg_conf:.2f}, "
        f"final={decision}, num_entries={num_entries}"
    )

    return {
        "decision": decision,
        "confidence": avg_conf,
        "scalp": scalp_res,
        "day": day_res,
        "swing": swing_res,
        "mode": mode,
        "weights": weights_final,
        "score": total_score,
        "num_entries": num_entries,
        "threshold": threshold,
        "regime": regime,
    }


class MetaIntegrator:
    def __init__(self, model_path: str):
        try:
            self.model = joblib.load(model_path)
            self.classes_ = list(self.model.classes_) if hasattr(self.model, "classes_") else ["BUY","SELL","HOLD"]
            logger.info(f"[MetaIntegrator] model loaded → {model_path}")
        except Exception as e:
            logger.error(f"[MetaIntegrator] load fail: {e}")
            self.model = None
            self.classes_ = ["BUY","SELL","HOLD"]

    def _encode_dec(self, d: str) -> int:
        if d == "BUY": return 1
        if d == "SELL": return -1
        return 0

    def _featurize(self, scalp_res, day_res, swing_res, entry: Any, regime: str):
        feats = [
            self._encode_dec(scalp_res.get("decision")),
            scalp_res.get("confidence", 0.0),
            self._encode_dec(day_res.get("decision")),
            day_res.get("confidence", 0.0),
            self._encode_dec(swing_res.get("decision")),
            swing_res.get("confidence", 0.0),
            getattr(entry, "atr", 0.0),
            getattr(entry, "adx", 0.0),
        ]
        regimes = ["trend", "range", "high_vol", "low_vol", "normal"]
        feats.extend([1 if regime == r else 0 for r in regimes])
        return np.array(feats, dtype=float)

    def integrate(self, scalp_res, day_res, swing_res, entry, regime: str = "normal") -> Dict[str, Any]:
        if self.model is None:
            return {"decision": "HOLD", "proba": 0.33, "raw": {}}

        X = self._featurize(scalp_res, day_res, swing_res, entry, regime).reshape(1, -1)
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)[0]
                idx = int(np.argmax(proba))
                decision = self.classes_[idx]
                return {"decision": decision, "proba": float(proba[idx]), "raw": dict(zip(self.classes_, proba))}
            else:
                pred = self.model.predict(X)[0]
                return {"decision": str(pred), "proba": 0.5, "raw": {}}
        except Exception as e:
            logger.error(f"[MetaIntegrator] predict fail: {e}")
            return {"decision": "HOLD", "proba": 0.0, "raw": {}}


integrate = integrate_decisions
