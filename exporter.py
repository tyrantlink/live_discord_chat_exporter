from models import Export,Guild,Channel,DateRange,Message,User,Role,Attachment,Embed,Sticker,Reaction,ReactionEmoji,ReactionUser,MessageReference,MESSAGE_TYPES,CHANNEL_TYPES,STICKER_TYPES
from discord import TextChannel,VoiceChannel,Thread,Message as DiscordMessage,Member,User as DiscordUser,Colour,NotFound,Guild as DiscordGuild
from datetime import datetime,timezone,timedelta
from typing import Callable,TypeVar,ParamSpec
from emoji_index import EMOJI_INDEX
from time import perf_counter
from functools import wraps
from inspect import stack
from config import DEBUG
from cache import Cache
from re import finditer

P = ParamSpec("P")
T = TypeVar("T")

GuildChannel = TextChannel|VoiceChannel|Thread

timed_functions = set()
printed_logs = []
time_taken = {}

def _get_real_parent() -> str|None:
	for frame in stack():
		if frame.function in timed_functions:
			return frame.function
	return None

def timer(func:Callable[P,T]) -> Callable[P,T]:
	timed_functions.add(func.__name__)
	@wraps(func)
	def wrapper_function(*args:P.args,**kwargs:P.kwargs) -> T: 
		st = perf_counter()
		value = func(*args,  **kwargs)
		if func.__name__ not in time_taken:
			time_taken[func.__name__] = 0
		et = perf_counter()-st
		time_taken[func.__name__] += et
		parent_func = _get_real_parent(func.__name__)
		if parent_func:
			if parent_func not in time_taken:
				time_taken[parent_func] = 0
			time_taken[parent_func] -= et
		return value
	return wrapper_function if DEBUG else func

def a_timer(func:Callable[P,T]) -> Callable[P,T]:
	timed_functions.add(func.__name__)
	@wraps(func)
	async def wrapper_function(*args:P.args,**kwargs:P.kwargs) -> T: 
		st = perf_counter()
		value = await func(*args,  **kwargs)
		if func.__name__ not in time_taken:
			time_taken[func.__name__] = 0
		et = perf_counter()-st
		time_taken[func.__name__] += et
		parent_func = _get_real_parent(func.__name__)
		if parent_func:
			if parent_func not in time_taken:
				time_taken[parent_func] = 0
			time_taken[parent_func] -= et
		return value
	return wrapper_function if DEBUG else func

class Exporter:
	def __init__(self,cache:Cache,channel:GuildChannel|None=None,always_use_username:bool=False,guild:DiscordGuild|None=None):
		if not channel and not guild:
			raise ValueError('either channel or guild must be provided')
		self.cache = cache
		self.channel = channel
		self.guild = guild or channel.guild
		self.always_use_username = always_use_username
		self.tz = timezone(timedelta(hours=0))

	@a_timer
	async def export(self) -> Export:
		if self.channel is None:
			raise ValueError('cannot run full export without a channel')
		st = perf_counter()
		messages = await self._get_messages()
		export = Export(
			guild = self._get_guild(),
			channel = self._get_channel(),
			dateRange = self._get_date_range(),
			exportedAt = self._get_time(datetime.now()),
			messages = messages,
			messageCount = len(messages))
		if DEBUG:
			for key in sorted(time_taken,key=lambda k:time_taken[k],reverse=True):
				print(f'{key}: {time_taken[key]:.4f}s')
			print(f'total time taken: {perf_counter()-st:.4f}s')
		return export

	@timer
	def _get_time(self,time:datetime) -> str: #? stupid dumb bullshit to match dce exactly
		time = time.astimezone(self.tz)
		out_string = time.strftime('%Y-%m-%dT%H:%M:%S.')
		out_string += time.strftime('%f').rstrip('0')[:4] or '0'
		tz = time.strftime('%z')
		out_string += f'{tz[:-2]}:{tz[-2:]}'
		return out_string

	@timer
	def _get_guild(self) -> Guild:
		return Guild(
			id = str(self.guild.id),
			name = self.guild.name,
			iconUrl = str(self.guild.icon.with_size(512).url) if self.guild.icon else None)

	@timer
	def _get_channel(self) -> Channel:
		return Channel(
			id = str(self.channel.id),
			type = CHANNEL_TYPES.get(self.channel.type.value),
			categoryId = str(self.channel.parent.id if getattr(self.channel,'parent',None) else self.channel.category.id),
			category = self.channel.parent.name if getattr(self.channel,'parent',None) else self.channel.category.name,
			name = self.channel.name,
			topic = getattr(self.channel,'topic',None))

	@timer
	def _get_date_range(self) -> DateRange:
		return DateRange(
			after = None,
			before = None)

	@timer
	def _get_color_value(self,color:Colour) -> str|None:
		color_value = f'#{color.value:06x}'.upper()
		return None if color_value == '#000000' else color_value
	
	@a_timer
	async def _safe_fetch_member(self,id:int) -> Member|None:
		try:
			return (
				self.guild.get_member(id) or
				await self.guild.fetch_member(id)
			)
		except NotFound: return None

	@a_timer
	async def _get_author(self,author:Member|DiscordUser) -> User:
		if author.id in self.cache.authors:
			return self.cache.authors[author.id]
		if isinstance(author,DiscordUser) and author.id not in self.cache.members:
			self.cache.members[author.id] = await self._safe_fetch_member(author.id) or author
		author = self.cache.members.get(author.id,author)
		user = User(
			id = str(author.id),
			name = author.name,
			discriminator = '0000' if author.discriminator == '0' else author.discriminator, #? match dce exactly
			nickname = author.name if self.always_use_username else author.display_name, 
			color = self._get_color_value(author.color),
			isBot = author.bot,
			roles = [],
			avatarUrl = author.display_avatar.with_size(512).url)
		if isinstance(author,Member):
			user.roles = [Role(
				id = str(role.id),
				name = role.name,
				color = self._get_color_value(role.color),
				position = role.position
			) for role in sorted(author.roles[1:],key=lambda r:r.position,reverse=True)]
		self.cache.authors[author.id] = user
		return user

	@timer
	def _get_embeds(self,message:DiscordMessage) -> list[Embed]:
		embeds = []
		for embed in message.embeds:
			new_embed = Embed(
				title = embed.title or '',
				url = embed.url,
				timestamp = self._get_time(embed.timestamp) if embed.timestamp else None,
				description = embed.description or '')

			if embed.color:
				new_embed.color = self._get_color_value(embed.color)

			if embed.author:
				embed_author = {
					'name': embed.author.name,
					'url': embed.author.url}
				if embed.author.icon_url:
					embed_author['iconUrl'] = embed.author.icon_url
				if embed.author.proxy_icon_url:
					embed_author['iconProxyUrl'] = embed.author.proxy_icon_url
				new_embed.author = embed_author

			if embed.thumbnail:
				new_embed.thumbnail = {
					'url': embed.thumbnail.proxy_url,
					'width': embed.thumbnail.width,
					'height': embed.thumbnail.height}

			if embed.video:
				new_embed.video = {
					'url': embed.video.proxy_url or embed.video.url,
					'width': embed.video.width,
					'height': embed.video.height}

			if embed.footer:
				embed_footer = {
					'text': embed.footer.text}
				if embed.footer.icon_url:
					embed_footer['iconUrl'] = embed.footer.icon_url
				if embed.footer.proxy_icon_url:
					embed_footer['iconProxyUrl'] = embed.footer.proxy_icon_url
				new_embed.footer = embed_footer

			# if embed.image

			new_embed.fields = [{
				'name': field.name,
				'value': field.value,
				'isInline': field.inline
			} for field in embed.fields]

			embeds.append(new_embed)

		return embeds

	@a_timer
	async def _get_reaction_user(self,user:Member|DiscordUser) -> ReactionUser:
		if user.id in self.cache.reaction_users:
			return self.cache.reaction_users[user.id]
		if isinstance(user,DiscordUser) and user.id not in self.cache.members:
			self.cache.members[user.id] = await self._safe_fetch_member(user.id) or user
		user = self.cache.members.get(user.id,user)
		reaction_user = ReactionUser(
			id = str(user.id),
			name = user.name,
			discriminator = '0000' if user.discriminator == '0' else user.discriminator, #? match dce exactly
			nickname = user.name if self.always_use_username else user.display_name,
			isBot = user.bot,
			avatarUrl = user.display_avatar.with_size(512).url)
		self.cache.reaction_users[user.id] = reaction_user
		return reaction_user

	@a_timer
	async def _get_reactions(self,message:DiscordMessage) -> list[Reaction]:
		reactions = [
			Reaction(
				emoji = ReactionEmoji(
					id = str(reaction.emoji.id) if reaction.is_custom_emoji() else '',
					name = reaction.emoji.name if reaction.is_custom_emoji() else reaction.emoji,
					code = reaction.emoji.name if reaction.is_custom_emoji() else EMOJI_INDEX.get(reaction.emoji,''),
					isAnimated = reaction.emoji.animated if reaction.is_custom_emoji() else False,
					imageUrl = reaction.emoji.url if reaction.is_custom_emoji() else None),
				count = reaction.count,
				users = [await self._get_reaction_user(user) async for user in reaction.users()])
			for reaction in message.reactions]
		return reactions

	@a_timer
	async def get_message(self,message:DiscordMessage) -> Message:
		author = await self._get_author(message.author)

		#? there's probably a way to do this with just re.sub but that would be a very big one-liner and i don't want to do that
		content = message.content
		for match in finditer(r'(<@!?(\d+)>)',content):
			mention_user = await self._safe_fetch_member(int(match.group(2)))
			if mention_user is None:
				continue
			mention_data = await self._get_author(mention_user)
			content = content.replace(match.group(1),f'@{mention_data.name}')

		parsed_message = Message(
			id = str(message.id),
			type = MESSAGE_TYPES.get(message.type.value,'Default'),
			timestamp = self._get_time(message.created_at),
			timestampEdited = self._get_time(message.edited_at) if message.edited_at else None,
			callEndedTimestamp = None,
			isPinned = message.pinned,
			content = content,
			author = author,
			attachments = [Attachment(
				id = str(attachment.id),
				url = attachment.url,
				fileName = attachment.filename,
				fileSizeBytes = attachment.size)
				for attachment in message.attachments],
			embeds = self._get_embeds(message),
			stickers = [Sticker(
				id = str(sticker.id),
				name = sticker.name,
				format = STICKER_TYPES.get(sticker.format.value),
				sourceUrl = sticker.url)
				for sticker in message.stickers],
			reactions = await self._get_reactions(message),
			mentions = [await self._get_author(mention) for mention in message.mentions])

		if message.reference:
			parsed_message.reference = MessageReference(
				messageId = str(message.reference.message_id),
				channelId = str(message.reference.channel_id),
				guildId = str(message.reference.guild_id))

		return parsed_message

	@a_timer
	async def _get_messages(self) -> list[Message]:
		return [
			await self.get_message(message)
			async for message in self.channel.history(limit=None,oldest_first=True)]