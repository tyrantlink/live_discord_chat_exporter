from config import BOT_TOKEN,EXPORT_GUILD,EXPORT_DIRECTORY,CHATANALYTICS_DIRECTORY,EXPORT_THREAD_COUNT,EXCLUDED_CHANNELS
from discord import Client as DiscordClient,TextChannel,VoiceChannel,Thread,Message,Intents
from asyncio import gather,Semaphore,create_subprocess_exec
from models import Save,Export,Message as ExportMessage
from discord.ext.tasks import loop
from aiofiles import open as aopen
from exporter import Exporter
from json import dumps,loads
from os.path import exists
from pathlib import Path
from cache import Cache
from time import time


VALID_CHANNEL = TextChannel|VoiceChannel|Thread

class Client(DiscordClient):
	def __init__(self) -> None:
		super().__init__(intents=Intents.all()) #? doesn't need all, just messages and guild members, but i'm lazy
		self.cache = Cache()
		self.currently_exporting = False
		with open('save.json','r') as f:
			self.save = Save(**loads(f.read()))
		self.pending_exports:dict[int,list[ExportMessage]] = {}
		self.export_save:dict[int,Export] = {}

	async def on_ready(self) -> None:
		print('connected to discord!')
		self.export_guild = self.get_guild(EXPORT_GUILD)
		self.base_exporter = Exporter(self.cache,guild=self.export_guild)
		if not self.export_guild:
			await self.close()
			exit('could not find export guild')
		if not self.full_export_loop.is_running():
			self.full_export_loop.start()
		if not self.live_export_loop.is_running():
			self.live_export_loop.start()

	async def on_message(self,message:Message) -> None:
		await self._ready.wait()
		exported_message = await self.base_exporter.get_message(message)
		if message.channel.id not in self.pending_exports:
			self.pending_exports[message.channel.id] = []
		self.pending_exports[message.channel.id].append(exported_message)

	async def export_channel(self,channel:VALID_CHANNEL) -> None:
		exporter = Exporter(self.cache,channel,True)
		export = await exporter.export()
		if export.messageCount == 0:
			return
		self.export_save[channel.id] = export
		async with aopen(f'{EXPORT_DIRECTORY}/{channel.id}.json','w') as f:
			await f.write(dumps(export.model_dump_json_filter_missing(),indent=2,ensure_ascii=False))
		self.channels_export_progress[0] += 1
		print(f'({self.channels_export_progress[0]}/{self.channels_export_progress[1]}) exported {channel.name} ({channel.id})')

	async def export_thread_handler(self,semaphore:Semaphore,channel:VALID_CHANNEL) -> None:
		async with semaphore:
			await self.export_channel(channel)

	async def create_chatanalytics(self) -> None:
		process = await create_subprocess_exec('npx','chat-analytics','-p','discord','-i',f'{EXPORT_DIRECTORY}/*','-o',f'{CHATANALYTICS_DIRECTORY}/index.html')
		await process.wait()

	@loop(seconds=60)
	async def full_export_loop(self) -> None:
		await self._ready.wait()
		if self.currently_exporting:
			return
		if time() - self.save.last_full_export < 60*60*24*7:
			return
		print('7 days have passed since last full export, starting full export')
		self.currently_exporting = True

		channels = [
			c for c in self.export_guild.channels
			if isinstance(c,VALID_CHANNEL) and
			c.id not in EXCLUDED_CHANNELS and
			c.permissions_for(self.export_guild.me).read_message_history and
			c.permissions_for(self.export_guild.me).read_messages and
			not (isinstance(c,VoiceChannel) and not c.permissions_for(self.export_guild.me).connect)]

		self.channels_export_progress = [0,len(channels)]
		semaphore = Semaphore(EXPORT_THREAD_COUNT)
		tasks = [self.export_thread_handler(semaphore,channel) for channel in channels]
		await gather(*tasks)
		self.save.last_full_export = int(time())
		async with aopen('save.json','w') as f:
			f.write(self.save.model_dump_json(indent=2))
		self.currently_exporting = False

	@loop(minutes=5)
	async def live_export_loop(self) -> None:
		await self._ready.wait()
		if self.currently_exporting:
			return
		if not self.pending_exports:
			return
		for channel_id,messages in self.pending_exports.items():
			existing_export = self.export_save.get(channel_id,None)
			if existing_export is None:
				if not exists(f'{EXPORT_DIRECTORY}/{channel_id}.json'):
					continue
				async with aopen(f'{EXPORT_DIRECTORY}/{channel_id}.json','r') as f:
					#? crashes if i try to do model_validate_json, can't bother to figure out why
					existing_export = Export.model_validate(loads(await f.read()))
					self.export_save[channel_id] = existing_export

			for message in messages:
				if message.id in existing_export.messages[-1000:]:
					continue
				existing_export.messages.append(message)
			async with aopen(f'{EXPORT_DIRECTORY}/{channel_id}.json','w') as f:
				await f.write(dumps(existing_export.model_dump_json_filter_missing(),indent=2,ensure_ascii=False))
		self.pending_exports = {}
		await self.create_chatanalytics()

if __name__ == '__main__':
	Path.mkdir(Path(EXPORT_DIRECTORY),exist_ok=True)
	Path.mkdir(Path(CHATANALYTICS_DIRECTORY),exist_ok=True)

	if not exists('save.json'):
		with open('save.json','w') as f:
			f.write(dumps({'last_full_export':0},indent=2))

	Client().run(BOT_TOKEN,log_handler=None)