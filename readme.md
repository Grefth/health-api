# Como crear un API con Python y Git 

## Requisitos
- Python 3.12 o superior
- Git
- MongoDB (local o Atlas)
## Pasos para crear un API con Python y Git
1. Crea un nuevo repositorio en GitHub o en tu plataforma de control de versiones preferida.
2. Clona el repositorio en tu máquina local.
```bash
git clone <https://github.com/Grefth/health-api.git>
```
3. Creación del entorno virtual con `uv`
```bash
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
```
4. Instala las dependencias
```bash
uv pip install -r requirements.txt
```
5. Crea la estructura del proyecto
```
health-api/
├── app.py
├── requirements.txt
├── .gitignore
└── .venv/
```
6. Crea el archivo `.gitignore`
```
.venv/
__pycache__/
*.pyc
.env
.DS_Store
```
7. Inicializa Git y realiza el primer commit
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

# Routes
- /health
- /set_objective
- /image 
- /magic