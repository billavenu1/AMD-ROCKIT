#sample read me for my project

docker build -t amd-aria-app .
docker run -d -p 5055:5055 -p 8502:8502 --name aria-container amd-aria-app

# To access the UI: http://localhost:3000
# To access the Vision UI: http://localhost:8501
# Note: The Vision app might be using a different port (8501) depending on how it's run.
# The docker-compose.yml defines multiple services, check the 'ports' section for vision for the exact mapping.
