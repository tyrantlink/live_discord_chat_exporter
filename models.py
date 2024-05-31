from pydantic import BaseModel
from secrets import token_hex

class Missing:
	def __init__(self,seed:str):
		self.seed = seed

MISSING = Missing(token_hex(16))

CHANNEL_TYPES = {
	0:'GuildTextChat',
	1:'DirectTextChat',
	2:'GuildVoiceChat',
	3:'DirectGroupTextChat',
	4:'GuildCategory',
	5:'GuildNews',
	10:'GuildNewsThread',
	11:'GuildPublicThread',
	12:'GuildPrivateThread',
	13:'GuildStageVoice',
	14:'GuildDirectory',
	15:'GuildForum'
}

MESSAGE_TYPES = {
	0:'Default',
	1:'RecipientAdd',
	2:'RecipientRemove',
	3:'Call',
	4:'ChannelNameChange',
	5:'ChannelIconChange',
	6:'ChannelPinnedMessage',
	7:'GuildMemberJoin',
	18:'ThreadCreated',
	19:'Reply'
}

STICKER_TYPES = {
	1:'Png',
	2:'Apng',
	3:'Lottie',
	4:'Gif'
}

class BetterBaseModel(BaseModel):
	class Config:
		arbitrary_types_allowed = True
	
	def _remove_all_missing(self,d:dict) -> dict:
		for k,v in list(d.items()): #? list() to avoid modifying the dict while iterating
			if isinstance(v,dict):
				d[k] = self._remove_all_missing(v)
				continue
			if isinstance(v,list):
				d[k] = [self._remove_all_missing(e) for e in v]
				continue
			if v is MISSING:
				del d[k]
		return d
	
	def model_dump_json_filter_missing(self,*args,**kwargs):
		dump = self.model_dump(*args,**kwargs)
		return self._remove_all_missing(dump)

class SaveData(BetterBaseModel):
	last_full_archive:int

class Guild(BetterBaseModel):
	id:str
	name:str
	iconUrl:str|None

class Channel(BetterBaseModel):
	id:str
	type:str
	categoryId:str
	category:str
	name:str
	topic:str|None

class DateRange(BetterBaseModel):
	after:None
	before:None

class Role(BetterBaseModel):
	id:str
	name:str
	color:str|None
	position:int

class User(BetterBaseModel):
	id:str
	name:str
	discriminator:str
	nickname:str
	color:str|None
	isBot:bool
	roles:list[Role]|Missing = MISSING
	avatarUrl:str

class Attachment(BetterBaseModel):
	id:str
	url:str
	fileName:str
	fileSizeBytes:int

class Embed(BetterBaseModel):
	title:str
	url:str|None
	timestamp:str|None
	description:str
	color:str|Missing = MISSING
	author:dict|Missing = MISSING
	thumbnail:dict|Missing = MISSING
	video:dict|Missing = MISSING
	footer:dict|Missing = MISSING
	image:dict|Missing = MISSING
	images:list[dict] = []
	fields:list[dict] = []

class Sticker(BetterBaseModel):
	id:str
	name:str
	format:str
	sourceUrl:str

class ReactionEmoji(BetterBaseModel):
	id:str
	name:str
	code:str
	isAnimated:bool
	imageUrl:str|None

class ReactionUser(BetterBaseModel):
	id:str
	name:str
	discriminator:str
	nickname:str
	isBot:bool
	avatarUrl:str

class Reaction(BetterBaseModel):
	emoji:ReactionEmoji
	count:int
	users:list[ReactionUser] = []

class MessageReference(BetterBaseModel):
	messageId:str
	channelId:str
	guildId:str

class Message(BetterBaseModel):
	id:str
	type:str
	timestamp:str
	timestampEdited:str|None
	callEndedTimestamp:str|None
	isPinned:bool
	content:str
	author:User
	attachments:list[Attachment] = []
	embeds:list[Embed] = []
	stickers:list[Sticker] = []
	reactions:list[Reaction] = []
	mentions:list[User] = []
	reference:MessageReference|Missing = MISSING

class Export(BetterBaseModel):
	guild:Guild
	channel:Channel
	dateRange:DateRange
	exportedAt:str
	messages:list[Message]
	messageCount:int

class Save(BaseModel):
	last_full_export:int