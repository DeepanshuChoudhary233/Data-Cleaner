# Data Cleaner App

A web-based Data Cleaning Application built using HTML, CSS, and JavaScript that helps users preprocess datasets efficiently. The app supports CSV and ZIP file uploads and provides multiple data cleaning operations through an easy-to-use interface.

---

## Features

* Upload CSV or ZIP files
* Remove duplicate records
* Handle missing values intelligently:

  * If missing values are less than 5% → rows are removed
  * If missing values are between 5% and 30% → mean value imputation is used
  * If missing values are more than 30% → entire column is removed
* Remove outliers using the Box Plot (IQR) method
* Normalize data using Min-Max Normalization
* "Clean All" option to apply all preprocessing steps at once
* Automatically downloads cleaned dataset
* Displays cleaned data directly on screen

---

## Technologies Used

* HTML
* CSS
* JavaScript

---

## How It Works

1. Upload a CSV or ZIP file
2. Select desired cleaning operations
3. Click the process button
4. View cleaned data instantly
5. Cleaned file downloads automatically

---

## Data Cleaning Techniques Used

### 1. Duplicate Removal

Removes repeated rows from the dataset.

### 2. Missing Value Handling

The app uses percentage-based logic:

* `< 5%` missing values → remove rows
* `5% - 30%` missing values → replace with mean
* `> 30%` missing values → remove column

### 3. Outlier Removal

Uses the Interquartile Range (IQR) / Box Plot method to detect and remove outliers.

### 4. Normalization

Applies Min-Max Normalization to scale numeric values between 0 and 1.

---

## Future Improvements

* Add support for Excel files (.xlsx)
* Add visualization charts
* Add machine learning preprocessing techniques
* Backend integration for large datasets


## Author

Developed by Deepanshu Choudhary

---

## License

This project is open source and available under the MIT License.
