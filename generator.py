name: Generate Manga Catalog

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'mangas.json'
      - 'uploaded_cache.json'
      - 'README.md'
  workflow_dispatch:

permissions:
  contents: write
  actions: write

jobs:
  build-and-update:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pillow requests

      - name: Run Generator Script
        run: python generator.py

      - name: Commit and Push Changes
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          
          git fetch origin main
          
          # Truco definitivo: Crear los archivos temporalmente si no existen para evitar errores en Git
          touch uploaded_cache.json
          touch mangas.json
          mkdir -p catalog img
          
          git add catalog/ img/ mangas.json uploaded_cache.json
          
          if git diff --staged --quiet; then
            echo "No hay cambios para guardar."
          else
            git commit -m "auto: optimización, subida a ImgBB y actualización de catálogo [skip ci]"
            git push origin main --force-with-lease
          fi
