FROM python:3.11

WORKDIR /app

# install nodejs
RUN apt-get update -qq && apt-get -y install nodejs

# install chat-analytics
RUN npm install chat-analytics
RUN chmod +x /usr/bin/chat-ana-export

CMD python3.11 -u main.py