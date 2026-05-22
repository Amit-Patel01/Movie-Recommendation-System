# Data Folder

Place MovieLens data here:

```text
data/ml-latest-small/movies.csv
data/ml-latest-small/ratings.csv
```

Then import:

```bash
python -m ml.data_loader --dataset-dir data/ml-latest-small --clear
```

MovieLens provides `movieId`, `title`, `genres`, `userId`, `rating`, and `timestamp`.
Optional content metadata can be added with a CSV containing `movieId`, `overview`, `cast`, `director`, and `posterUrl`.

