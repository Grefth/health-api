import fastapi
import uvicorn

app = fastapi.FastAPI()

@app.get("/health")
def read_health():
    return {"status": "healthy"}

@app.get("/set_objective")
def set_objective():
    #TODO : implement objective setting logic
    return {"message": "Objective set successfully"}

@app.get("/image")
def read_image():
    #TODO : implement image retrieval logic
    return {"message": "Image retrieved successfully"}

@app.get("/magic")
def read_magic(numero: str):
    return {
        "Hello": numero,
        "edad": numero
    }


#TODO implemntar swagger documentation for the API endpoints
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)