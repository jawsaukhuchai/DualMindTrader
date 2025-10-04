# DualMindTrader – Developer Guide (Mind2: Python Bot)

This document provides an internal developer reference for the **Decision Engine** in DualMindTrader (Mind2).  
It summarizes the flow, coverage of unit tests, and logging conventions.

---

## 🔄 System Flow Overview

```mermaid
flowchart TD

    subgraph M1[Mind1 MT5 EA]
        A[Mind1_EA.mq5] --> B[mind1_feed.json]
    end

    subgraph M2[Mind2 Python Bot]
        B --> C[schema.py validate]
        C --> D[decision_engine.py]
        D -->|call| S1[scalp.py]
        D -->|call| S2[day.py]
        D -->|call| S3[swing.py]
        S1 --> D
        S2 --> D
        S3 --> D
        D --> E[Integration (majority/priority)]
        E --> F[Final Decision]
    end

    F --> G[Send Orders to MT5]

