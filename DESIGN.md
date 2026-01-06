# Design Specification: Momentum Detector Web App

## 1. Overview
This project aims to migrate an existing data analysis pipeline (Momentum Detector) from a Google Sheets-based workflow to a local Web Application using Streamlit. The application will run on a local machine (Macbook), download stock data, process it, and visualize the results.

## 2. System Architecture

The system consists of three main components:
1.  **Data Collection & Processing (Backend)**: Existing Python scripts that download and process stock data.
2.  **Data Storage**: Local file system (CSV files).
3.  **User Interface (Frontend)**: Streamlit application for data visualization and control.

### Directory Structure
```
.
├── app.py                  # Main Streamlit application
├── main.py                 # Orchestrator for data collection (modified)
├── 1-csv_downloader...py   # Step 1: Download Stock Data
├── 2-csv_downloader...py   # Step 2: Download Index Data
├── 3-data_processor...py   # Step 3: Process Data
├── data/                   # Data storage
│   ├── raw/                # Raw downloaded CSVs
│   └── processed_data/     # Processed summary CSVs
└── logs/                   # Log files
```

## 3. Functional Requirements

### 3.1 Data Collection
-   **Manual Trigger**: Users can trigger the data update process from the Web UI.
-   **Scheduled Execution**: (Optional) The backend can be run on a schedule, but the Web UI provides an on-demand interface.
-   **Process**:
    1.  Download Individual Stock Data (Step 1).
    2.  Download Index Data (Step 2).
    3.  Process and Aggregate Data (Step 3).
    4.  (Legacy Step 4 is removed).
    5.  (Optional) Run Analyzer/Notifier (Step 5/6).

### 3.2 Data Visualization
-   **Sector Summary**:
    -   Display table of sector performance (Rise/Fall counts, Weighted Average Return).
    -   Filter by Market Cap (Small, Mid, Large, Overall).
    -   Sortable columns.
-   **Momentum Summary**:
    -   Display Trading Value Momentum (e.g., 5-day/20-day average ratios).
    -   Highlight sectors with high momentum.

## 4. User Interface Design

### Sidebar
-   **Navigation**: "Dashboard", "Data Management".
-   **Status**: Display the date of the latest available data.

### Dashboard Page
-   **Header**: "Market Momentum Dashboard".
-   **Tab 1: Sector Analysis**:
    -   Table showing `sector_summary` data.
    -   Metrics: Top performing sectors today.
-   **Tab 2: Momentum Analysis**:
    -   Table showing `momentum_summary` data.
    -   Visualizations: Bar charts for momentum ratios.

### Data Management Page
-   **Action**: "Update Data" button.
-   **Logs**: Text area displaying the execution logs of the update process.

## 5. Technology Stack
-   **Language**: Python 3
-   **Web Framework**: Streamlit
-   **Data Manipulation**: Pandas
-   **HTTP Client**: Requests

## 6. Migration Steps
1.  **Environment Setup**: Install `streamlit` and dependencies.
2.  **Refactoring**: Ensure `main.py` can be triggered by Streamlit (or replicated functionality).
3.  **Frontend Development**: Implement `app.py`.
4.  **Testing**: Verify data flow from download to visualization.
