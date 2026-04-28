import pandas as pd
import os

def check_paths():
    csv_path = 'inzyts_test_datasets.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Columns that contain file paths
    path_columns = ['Data_Dictionary', 'File_1', 'File_2', 'File_3', 'File_4', 'File_5', 'File_6']
    
    missing_files = []
    
    print(f"Checking {len(df)} datasets...")
    print("-" * 60)

    for index, row in df.iterrows():
        dataset_name = row['Dataset_Name']
        for col in path_columns:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != '':
                path = str(row[col]).strip()
                if not os.path.exists(path):
                    missing_files.append({
                        'dataset': dataset_name,
                        'column': col,
                        'path': path
                    })
                    print(f"❌ MISSING: [{dataset_name}] {col} -> {path}")

    print("-" * 60)
    if not missing_files:
        print("✅ All files exist!")
    else:
        print(f"Found {len(missing_files)} missing files.")

if __name__ == "__main__":
    check_paths()
