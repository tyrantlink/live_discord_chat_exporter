FROM python:3.11

WORKDIR /app
COPY . .

# install nodejs
RUN apt-get update -qq && apt-get -y install nodejs npm

# install chat-analytics
RUN npm install chat-analytics

# install python dependencies
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

CMD python3.11 -u main.py