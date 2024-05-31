FROM python:3.11

WORKDIR /app

# install .net and nodejs
RUN curl -sL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
RUN apt-get update -qq && apt-get -y install \
	aspnetcore-runtime-8.0 \
	nodejs

# install discord chat exporter
RUN cd /app && mkdir -p dce && cd dce
RUN curl -Lo dce.zip https://github.com/Tyrrrz/DiscordChatExporter/releases/download/2.43.2/DiscordChatExporter.Cli.linux-x64.zip
RUN unzip dce.zip
RUN rm dce.zip
RUN echo "dotnet ~/dce/DiscordChatExporter.Cli.dll" > /usr/bin/dce
RUN chmod +x /usr/bin/dce

# install chat-analytics
RUN npm install chat-analytics
RUN chmod +x /usr/bin/chat-ana-export

CMD python3.11 -u main.py