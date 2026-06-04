from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import io
import os
import json
import zipfile

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

current_df = {}

def df_to_json(df):
    """Convert dataframe to JSON-serializable format, preserving all column types."""
    df_clean = df.copy()
    # Convert nullable/extension dtypes to plain object so text comes through
    for col in df_clean.columns:
        try:
            df_clean[col] = df_clean[col].astype(object)
        except Exception:
            pass

    rows = []
    for row in df_clean.itertuples(index=False):
        clean_row = []
        for val in row:
            if val is None:
                clean_row.append(None)
            elif isinstance(val, float) and pd.isna(val):
                clean_row.append(None)
            elif isinstance(val, (bool, int, float, str)):
                clean_row.append(val)
            else:
                try:
                    clean_row.append(val.item())   # numpy scalar → Python native
                except Exception:
                    v = str(val)
                    clean_row.append(None if v in ('nan', 'None', '<NA>') else v)
        rows.append(clean_row)

    return {
        "columns": df_clean.columns.tolist(),
        "data": rows,
        "shape": list(df_clean.shape)
    }

def get_missing_info(df):
    total = len(df)
    missing = df.isnull().sum()
    pct = (missing / total * 100).round(2)
    return missing, pct

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    filename = file.filename.lower()

    if not (filename.endswith('.csv') or filename.endswith('.zip')):
        return jsonify({"error": "Only .csv or .zip files are supported"}), 400

    try:
        if filename.endswith('.zip'):
            file_bytes = io.BytesIO(file.read())
            with zipfile.ZipFile(file_bytes) as zf:
                csv_names = [n for n in zf.namelist()
                             if n.lower().endswith('.csv') and not n.startswith('__MACOSX')]
                if not csv_names:
                    return jsonify({"error": "No CSV file found inside the ZIP"}), 400
                if len(csv_names) > 1:
                    return jsonify({"error": f"ZIP contains multiple CSV files: {csv_names}. Please zip only one CSV."}), 400
                with zf.open(csv_names[0]) as csv_file:
                    df = pd.read_csv(csv_file)
            source_name = csv_names[0]
        else:
            df = pd.read_csv(file)
            source_name = file.filename

        current_df['data'] = df
        missing, pct = get_missing_info(df)

        missing_info = []
        for col in df.columns:
            if missing[col] > 0:
                missing_info.append({
                    "column": col,
                    "missing_count": int(missing[col]),
                    "missing_pct": float(pct[col])
                })

        return jsonify({
            "message": f"File '{source_name}' uploaded successfully",
            "preview": df_to_json(df.head(10)),
            "full_data": df_to_json(df),
            "missing_info": missing_info,
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "columns": df.columns.tolist()
        })
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid or corrupted ZIP file"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/handle-missing', methods=['POST'])
def handle_missing():
    if 'data' not in current_df:
        return jsonify({"error": "No data uploaded"}), 400

    body = request.json
    preference = body.get('preference', 'row')

    df = current_df['data'].copy()
    changes = []
    missing, pct = get_missing_info(df)

    cols_to_drop = []
    for col in df.columns:
        p = pct[col]
        if p == 0:
            continue
        if p < 5:
            if preference == 'column':
                cols_to_drop.append(col)
                changes.append(f"Column '{col}' ({p}% missing) → dropped column")
            else:
                before = int(df[col].isnull().sum())
                df = df.dropna(subset=[col])
                changes.append(f"Column '{col}' ({p}% missing) → dropped {before} rows")
        elif p <= 30:
            if pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                changes.append(f"Column '{col}' ({p}% missing) → filled with mean ({mean_val:.4f})")
            else:
                mode_val = df[col].mode()[0]
                df[col] = df[col].fillna(mode_val)
                changes.append(f"Column '{col}' ({p}% missing) → filled with mode ('{mode_val}')")
        else:
            cols_to_drop.append(col)
            changes.append(f"Column '{col}' ({p}% missing > 30%) → dropped entire column")

    df = df.drop(columns=cols_to_drop)
    current_df['data'] = df

    return jsonify({
        "message": "Missing values handled",
        "changes": changes,
        "full_data": df_to_json(df),
        "shape": list(df.shape)
    })

@app.route('/remove-duplicates', methods=['POST'])
def remove_duplicates():
    if 'data' not in current_df:
        return jsonify({"error": "No data uploaded"}), 400

    df = current_df['data'].copy()
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    current_df['data'] = df

    return jsonify({
        "message": f"Removed {before - after} duplicate rows",
        "removed": before - after,
        "full_data": df_to_json(df),
        "shape": list(df.shape)
    })

@app.route('/remove-outliers', methods=['POST'])
def remove_outliers():
    if 'data' not in current_df:
        return jsonify({"error": "No data uploaded"}), 400

    body = request.json
    column = body.get('column', '').strip()
    df = current_df['data'].copy()

    if column not in df.columns:
        return jsonify({"error": f"Column '{column}' not found in data"}), 400

    if not pd.api.types.is_numeric_dtype(df[column]):
        # Try to coerce — handles cases like " 88.5" (spaces) or mixed object columns
        coerced = pd.to_numeric(df[column], errors='coerce')
        if coerced.isnull().all():
            return jsonify({"error": f"Column '{column}' is not numeric. Outlier removal requires a numeric column."}), 400
        df[column] = coerced
        current_df['data'] = df

    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    before = len(df)
    # Keep rows that are within bounds OR have NaN (don't silently drop missing rows)
    df = df[((df[column] >= lower) & (df[column] <= upper)) | df[column].isnull()]
    after = len(df)
    current_df['data'] = df

    return jsonify({
        "message": f"Removed {before - after} outlier rows from '{column}'",
        "column": column,
        "Q1": round(float(Q1), 4),
        "Q3": round(float(Q3), 4),
        "IQR": round(float(IQR), 4),
        "lower_bound": round(float(lower), 4),
        "upper_bound": round(float(upper), 4),
        "removed": before - after,
        "full_data": df_to_json(df),
        "shape": list(df.shape)
    })

@app.route('/normalize', methods=['POST'])
def normalize():
    if 'data' not in current_df:
        return jsonify({"error": "No data uploaded"}), 400

    body = request.json
    column = body.get('column', '').strip()
    df = current_df['data'].copy()

    if column not in df.columns:
        return jsonify({"error": f"Column '{column}' not found in data"}), 400

    if not pd.api.types.is_numeric_dtype(df[column]):
        return jsonify({"error": f"Column '{column}' is not numeric. Normalization requires a numeric column."}), 400

    col_min = df[column].min()
    col_max = df[column].max()

    if col_max == col_min:
        return jsonify({"error": f"Column '{column}' has all identical values. Cannot normalize."}), 400

    df[column] = (df[column] - col_min) / (col_max - col_min)
    current_df['data'] = df

    return jsonify({
        "message": f"Min-Max normalization applied to '{column}'",
        "column": column,
        "original_min": round(float(col_min), 4),
        "original_max": round(float(col_max), 4),
        "full_data": df_to_json(df),
        "shape": list(df.shape)
    })

@app.route('/preprocess-all', methods=['POST'])
def preprocess_all():
    if 'data' not in current_df:
        return jsonify({"error": "No data uploaded"}), 400

    body = request.json
    preference = body.get('preference', 'row')
    outlier_columns = body.get('outlier_columns', [])
    normalize_columns = body.get('normalize_columns', [])

    df = current_df['data'].copy()
    log = []

    # Step 1: Handle missing values
    missing, pct = get_missing_info(df)
    cols_to_drop = []
    for col in df.columns:
        p = pct[col]
        if p == 0:
            continue
        if p < 5:
            if preference == 'column':
                cols_to_drop.append(col)
                log.append(f"[Missing] Column '{col}' ({p}% < 5%) → dropped column")
            else:
                before = int(df[col].isnull().sum())
                df = df.dropna(subset=[col])
                log.append(f"[Missing] Column '{col}' ({p}% < 5%) → dropped {before} rows")
        elif p <= 30:
            if pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                log.append(f"[Missing] Column '{col}' ({p}%) → filled with mean ({mean_val:.4f})")
            else:
                mode_val = df[col].mode()[0]
                df[col] = df[col].fillna(mode_val)
                log.append(f"[Missing] Column '{col}' ({p}%) → filled with mode ('{mode_val}')")
        else:
            cols_to_drop.append(col)
            log.append(f"[Missing] Column '{col}' ({p}% > 30%) → dropped column")

    df = df.drop(columns=cols_to_drop)

    # Step 2: Remove duplicates
    before = len(df)
    df = df.drop_duplicates()
    log.append(f"[Duplicates] Removed {before - len(df)} duplicate rows")

    # Step 3: Remove outliers
    for col in outlier_columns:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            before = len(df)
            df = df[((df[col] >= lower) & (df[col] <= upper)) | df[col].isnull()]
            log.append(f"[Outliers] Column '{col}' → removed {before - len(df)} outlier rows")

    # Step 4: Normalize
    for col in normalize_columns:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            col_min = df[col].min()
            col_max = df[col].max()
            if col_max != col_min:
                df[col] = (df[col] - col_min) / (col_max - col_min)
                log.append(f"[Normalize] Column '{col}' → Min-Max normalization applied")

    current_df['data'] = df

    return jsonify({
        "message": "Full preprocessing pipeline completed",
        "log": log,
        "full_data": df_to_json(df),
        "shape": list(df.shape)
    })

@app.route('/download', methods=['GET'])
def download():
    if 'data' not in current_df:
        return jsonify({"error": "No data to download"}), 400

    df = current_df['data']
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='preprocessed_data.csv'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)