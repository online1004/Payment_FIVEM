# coding=utf-8

import nextcord, json
from nextcord.ext import commands
from nextcord.ui import View
from nextcord import Embed, Interaction,Button,ButtonStyle
from discord_webhook import DiscordWebhook, DiscordEmbed
import requests , sqlite3, aiomysql

intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

####### config #######
config = open('./config.json', 'r', encoding='utf-8') 
config_data = json.loads(config.read())

TOKEN = config_data['TOKEN'] # 봇토큰
GUILD_ID = int(config_data['GUILD_ID']) # 길드 ID 
SERVER_NAME = config_data['SERVER_NAME'] # 서버이름
ICON_URL = config_data['ICON_URL'] # 아이콘 url

TOSS_TOKEN = config_data['toss'][0]['TOSS_TOKEN'] # 토스 api 토큰
TOSS_ID = config_data['toss'][0]['TOSS_ID'] # 토스 ID 

CHARGE_LOG = config_data['webhook'][0]['CHARGE_LOG'] # 충전로그 
BUY_LOG = config_data['webhook'][0]['BUY_LOG'] # 구매로그

host = config_data['database'][0]['host']
user = config_data['database'][0]['user']
password = config_data['database'][0]['password']
db = config_data['database'][0]['db']
port = config_data['database'][0]['port']

####### 시스템 데이터베이스 #######
conn = sqlite3.connect("./database.db")

####### 서버 데이터베이스 #######
async def connect_mysql():
    connection = await aiomysql.connect(host=host, user=user, password=password, db=db, port=int(port), autocommit=True)
    cur = await connection.cursor()
    return cur

####### 컬쳐랜드 문화상품권 자동충전 모달 #######
class 계좌확인모달(nextcord.ui.Modal):
    def __init__(self):
        super().__init__(
            "계좌이체 자동충전",
        )
        self.pin_num = nextcord.ui.TextInput(label= "입금자명 입력란", min_length=6, max_length=6, required=True, placeholder= '안내해드린 입금자명 6자리를 붙혀넣기 해주세요.', style= nextcord.TextInputStyle.paragraph)
        self.add_item(self.pin_num)
    async def callback(self, interaction: nextcord.Interaction) -> None:
        try:
            header = { "token": TOSS_TOKEN }
            pin_num = self.pin_num.value
            TOSS_API_URL_RESULT = 'http://domain/api/toss/confirm' # 결과 가져오기
            text = {"code": str(pin_num)}
            res  = requests.post(TOSS_API_URL_RESULT, json=text, headers=header)
            RES_JSON = res.json()
            RES_RESULT = RES_JSON['result']
            RES_MESSAGE = RES_JSON['message']
            if RES_RESULT == 'SUCCESS':
                cur = conn.cursor()
                cur.execute(f"SELECT user_id FROM user WHERE user.user_id == '{interaction.user.id}'")
                if cur.fetchone() == None:
                    em = nextcord.Embed(title=f'{SERVER_NAME} 계좌이체 충전 안내', description=f'**{RES_MESSAGE}**원이 성공적으로 입금되었습니다.\n잔액은 **{RES_MESSAGE}**원 입니다.')
                    cur.execute(f"INSERT INTO user Values({int(interaction.user.id)}, {int(RES_MESSAGE)});")
                    conn.commit()
                    WebEmbed = DiscordEmbed(
                        title=f"{SERVER_NAME} 충전로그",
                        description=f"```충전한 유저 : {interaction.user}\n충전한 유저 ID : {interaction.user.id}\n충전한 금액 : {RES_MESSAGE} 원\n총 잔여금액 : {RES_MESSAGE} 원```"
                        )
                    WebEmbed.set_footer(text=f"CopyRight 2022. {SERVER_NAME}. All rights reserved.", icon_url=ICON_URL)
                    webhook = DiscordWebhook(url=f'{CHARGE_LOG}')
                    webhook.add_embed(WebEmbed)
                    webhook.execute()
                    return await interaction.response.send_message(embed=em, ephemeral=True)
                else:
                    cur.execute(f"SELECT money FROM user WHERE user.user_id = {int(interaction.user.id)}")
                    TupleData = cur.fetchone()
                    MONEY = TupleData[0]
                    cur.execute(f"UPDATE user SET money={str(int(MONEY) + int(RES_MESSAGE))} where user_id={int(interaction.user.id)}")
                    conn.commit()
                    WebEmbed = DiscordEmbed(
                        title=f"{SERVER_NAME} 충전로그",
                        description=f"```충전한 유저 : {interaction.user}\n충전한 유저 ID : {interaction.user.id}\n충전한 금액 : {RES_MESSAGE} 원\n총 잔여금액 : {str(int(MONEY) + int(RES_MESSAGE))} 원```"
                        )
                    WebEmbed.set_footer(text=f"CopyRight 2022. {SERVER_NAME}. All rights reserved.", icon_url=ICON_URL)
                    webhook = DiscordWebhook(url=f'{CHARGE_LOG}')
                    webhook.add_embed(WebEmbed)
                    webhook.execute()
                    em = nextcord.Embed(title=f'{SERVER_NAME} 계좌이체 충전 안내', description=f'**{RES_MESSAGE}**원이 성공적으로 입금되었습니다.\n잔액은 **{str(int(MONEY) + int(RES_MESSAGE))}**원 입니다.')
                    return await interaction.response.send_message(embed=em, ephemeral=True)
            elif RES_RESULT == 'FAIL':
                em = nextcord.Embed(title=f'{SERVER_NAME} 계좌이체 충전 안내', description=f'{RES_MESSAGE}')
                return await interaction.response.send_message(embed=em, ephemeral=True)
        except Exception as e:
            print(e)
            return await interaction.response.send_message(f'오류가 발생하였습니다. 오류 내용은 {e}', ephemeral=True)

####### 토스뱅크 가상계좌 요청폼 #######
class 토스뱅크확인(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    @nextcord.ui.button(label = '확인하기', style=nextcord.ButtonStyle.green)
    async def 확인하기(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        view = 계좌확인모달()
        await interaction.response.send_modal(view)
        self.value = False
        self.stop()

####### 토스뱅크 가상계좌 자동충전 모달 #######
class 토스뱅크모달(nextcord.ui.Modal):
    def __init__(self):
        super().__init__(
            "계좌이체 자동충전",
        )
        self.money_num = nextcord.ui.TextInput(label= "계좌이체 요청금액", min_length=1, max_length=10, required=True, placeholder= '금액을 숫자로만 입력해주세요. EX) 10000', style= nextcord.TextInputStyle.paragraph)
        self.add_item(self.money_num)
    async def callback(self, interaction: nextcord.Interaction) -> None:
        money_num = self.money_num.value
        try:
            jsons = {"id": TOSS_ID,"amount": str(money_num)}
            TOSS_API_URL_RESPONSE = 'http://domain/api/toss/request' # 요청하기
            header = { "token": TOSS_TOKEN }
            res  = requests.post(TOSS_API_URL_RESPONSE, json=jsons, headers=header)
            PAY_JSON = res.json()
            PAY_NAME = PAY_JSON['code']
            PAY_ACC = PAY_JSON['accNumber']
            view = 토스뱅크확인()
            embed = nextcord.Embed (
            title = f'{SERVER_NAME} 계좌 안내',
            description= f'**```* 주의 *\n아래 버튼을 누르기 전, 입금자명을 미리 복사해주세요 !\n입금자명을 꼭 변경하여 입금하여 주세요.\n입금을 완료하시고 확인버튼을 눌러주세요.\n입금 시스템은 요청 후 5분뒤 마감되니, 빠르게 입금해주세요.\n\n입금자명이 유출되지 않도록 조심해주세요.```**\n**```계좌번호 : {PAY_ACC}\n예금주 : {TOSS_ID}\n요청금액 : {money_num} 원\n입금자명 : {PAY_NAME}```**'
            )
            return await interaction.response.send_message(embed=embed,view=view, ephemeral=True)
        except Exception as e:
            print(e)

####### 토스뱅크 가상계좌 요청폼 #######
class 토스뱅크(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    @nextcord.ui.button(label = '요청하기', style=nextcord.ButtonStyle.green)
    async def 요청하기(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_modal(토스뱅크모달())
        self.value = False
        self.stop()

####### 충전방식 선택용 버튼 #######
class 충전시스템(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    @nextcord.ui.button(label = '계좌이체', style=nextcord.ButtonStyle.green)
    async def 계좌이체(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        view = 토스뱅크()
        embed = nextcord.Embed(
        title=f"{SERVER_NAME} 후원시스템",
        description=f"```1. 아래에 요청 버튼을 눌러 모달을 통해 충전을 요청해주세요\n2. 아래 출력된 메시지에 안내사항을 확인하고 입금해주세요```"
        )   
        await interaction.response.send_message(embed=embed,view=view, ephemeral=True)
        self.value = True
        self.stop()

####### 상품구매 전용 버튼 #######
class 제품구매하기(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    @nextcord.ui.button(label = '결제', style=nextcord.ButtonStyle.green)
    async def 결제(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.value = True
        self.stop()
    @nextcord.ui.button(label = '취소', style=nextcord.ButtonStyle.green)
    async def 취소(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message('상품 구매가 취소되었습니다.', ephemeral=True)
        self.value = False
        self.stop()


@bot.event
async def on_ready():
    print(f'{SERVER_NAME} 자동 후원 시스템이 시작되었습니다.')

@bot.slash_command(description=f"{SERVER_NAME} 후원금액 충전", guild_ids=[GUILD_ID])
async def 충전하기(interaction: nextcord.Interaction):
    embed = nextcord.Embed(
        title=f"{SERVER_NAME} 후원시스템",
        description=f"**{interaction.user}** 님, 안녕하세요 !\n```css\n해당 후원 시스템 이용방법을 안내드리겠습니다.\n1. 원하시는 후원방식을 선택해주세요.\n2. 안내에 따라 입금 혹은 컬쳐랜드 핀번호 입력을 진행해주세요.\n\n* 주의사항 *\n결제 전, 결제 방법을 확실하게 확인해주세요.\n정확하지 않은 결제방법을 이용하여, 정상적으로 결제되지 아니하는 경우엔 보상하지 않습니다.\n\n언제나 저희 {SERVER_NAME} 를 응원해주셔서 진심으로 감사드립니다.```"
    )
    embed.set_footer(text=f"CopyRight 2022. {SERVER_NAME}. All rights reserved.", icon_url=f'{ICON_URL}')
    view = 충전시스템()
    await interaction.send(embed=embed, view=view, ephemeral=True)
    await view.wait()

@bot.slash_command(description=f"{SERVER_NAME} 후원잔액 확인", guild_ids=[GUILD_ID])
async def 잔액확인(interaction: nextcord.Interaction):
    cur = conn.cursor()
    cur.execute(f"SELECT user_id FROM user WHERE user.user_id == '{interaction.user.id}'")
    if cur.fetchone() == None:
        embed = nextcord.Embed(
        title="오류 발생 알림",
        description=f"유저의 정보가 조회되지 않았습니다.\n후원 내역이 존재하지 않거나, 데이터를 인식하지 못하였습니다.\n오류로 판단된다면 관리자에게 문의해주세요."
        )
        return await interaction.send(embed=embed, ephemeral=True)
    else:
        cur.execute(f"SELECT money FROM user WHERE user.user_id = {int(interaction.user.id)}")
        TupleData = cur.fetchone()
        MONEY = TupleData[0]
        embed = nextcord.Embed(
            title=f"{SERVER_NAME} 잔액확인 시스템",
            description=f"**{interaction.user}** 님의 잔액은 **{MONEY}** 원 입니다."
        )
        embed.set_footer(text=f"CopyRight 2022. {SERVER_NAME}. All rights reserved.", icon_url=f'{ICON_URL}')
        await interaction.send(embed=embed, ephemeral=True)

@bot.slash_command(description=f"{SERVER_NAME} 후원상품 확인", guild_ids=[GUILD_ID])
async def 상품확인(interaction: nextcord.Interaction):
    embed = nextcord.Embed (
        title=f'{SERVER_NAME} 후원상품 안내',
        description='**```ansi\n[0;34m- 후원 차량 목록 -[0m\n\n'
    )
    with open('./product.json', encoding='utf8') as f:
        product_data = json.load(f)
    for i in product_data:
        if product_data[i]['amount'] == '0':
            return
        embed.description += f"[0;35m[ {i} : {product_data[i]['price']} 원 ]\n"
    embed.description += f"\n[0;37m언제나 저희 {SERVER_NAME} 를 응원해주셔서 진심으로 감사드립니다.[0m```**"
    await interaction.send(embed=embed, ephemeral=True)

@bot.slash_command(description=f"{SERVER_NAME} 후원상품 구매", guild_ids=[GUILD_ID])
async def 상품구매(interaction: nextcord.Interaction, 상품명: str, 고유번호: int):
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT user_id FROM user WHERE user.user_id == '{interaction.user.id}'")
        if cur.fetchone() == None:
            embed = nextcord.Embed(
            title="오류 발생 알림",
            description=f"유저의 정보가 조회되지 않았습니다.\n후원 내역이 존재하지 않거나, 데이터를 인식하지 못하였습니다.\n오류로 판단된다면 관리자에게 문의해주세요."
            )
            await interaction.send(embed=embed, ephemeral=True)
        else:
            try:
                with open('./product.json', encoding='utf8') as f:
                    product_data = json.load(f)
                if product_data[상품명]:
                    if product_data[상품명]['amount'] == 0:
                        return await interaction.send('잔여 재고가 존재하지 않습니다.', ephemeral=True)
                    cur.execute(f"SELECT money FROM user WHERE user.user_id = {int(interaction.user.id)}")
                    USER_MONEY = int(cur.fetchone()[0])
                    PRODUCT_PRICE = int(product_data[상품명]['price'])
                    if USER_MONEY >= PRODUCT_PRICE:
                        embed = nextcord.Embed(
                            title=f"{SERVER_NAME} 상품구매 안내",
                            description=f"**```css\n고유번호 : {고유번호} 번 / 상품명 : {상품명}\n\n위에 기재된 고유번호와 구매하실 상품명이 올바른지 확인해주세요.\n\n만일 올바르다면 ' 결제 ' 를 아니라면 ' 취소 ' 를 눌러주세요.```**"
                        )
                        view = 제품구매하기()
                        await interaction.send(embed=embed, view=view, ephemeral=True)
                        await view.wait()
                        if view.value:
                            try:
                                ## Using MySQL
                                curr = await connect_mysql()
                                await curr.execute(f"SELECT EXISTS (SELECT * FROM vrp_users where id = {고유번호}) as success")
                                result = await curr.fetchone()
                                if result[0] == 1:
                                    await curr.execute(f"INSERT INTO vrp_user_vehicles(user_id, vehicle, modifications) VALUES ('{고유번호}','{product_data[상품명]['code']}','')")
                                    # Using Sqlite3 And Webhook
                                    WebEmbed = DiscordEmbed(
                                    title=f"{SERVER_NAME} 구매로그",
                                    description=f"```구매한 유저 : {interaction.user}\n구매한 유저 ID : {interaction.user.id}\n지급한 고유번호 : {고유번호}\n구매한 상품명 : {상품명}```"
                                    )
                                    WebEmbed.set_footer(text=f"CopyRight 2022. {SERVER_NAME}. All rights reserved.", icon_url=ICON_URL)
                                    webhook = DiscordWebhook(url=f'{BUY_LOG}')
                                    webhook.add_embed(WebEmbed)
                                    webhook.execute()
                                    UPDATE_MONEY = USER_MONEY - PRODUCT_PRICE
                                    cur.execute(f"UPDATE user SET money={UPDATE_MONEY} where user_id={int(interaction.user.id)}")
                                    conn.commit()
                                    product_data[상품명]['amount'] = int(product_data[상품명]['amount']) - 1
                                    with open('./product.json', 'w', encoding='utf-8') as make_file:
                                        json.dump(product_data, make_file, indent="\t")
                                    await interaction.send('정상적으로 구매처리가 완료되었습니다.', ephemeral=True)
                                else:
                                    embed = nextcord.Embed(
                                        title="오류 발생 알림",
                                        description='유저 정보 식별 불가\n사용자의 고유번호가 확인되지 않았습니다.'
                                    )
                                    await interaction.send(embed=embed, ephemeral=True)
                            except Exception as e:
                                print(e)
                                await interaction.send('처리 도중 오류가 발생하였습니다.\n관리자에게 문의하여 주세요.', ephemeral=True)

                        elif view.value == False:
                            return
                    else:
                        embed = nextcord.Embed(
                        title="오류 발생 알림",
                        description=f"**```보유하고 있는 금액이 상품의 금액보다 작습니다.\n\n/충전하기 명령어를 사용하여 남은 금액을 충전하여 주세요.\n[ 추가 충전하셔야 하는 금액 : {PRODUCT_PRICE - USER_MONEY} 원 ]```**"
                        )
                        await interaction.send(embed=embed, ephemeral=True)
            except KeyError:
                embed = nextcord.Embed(
                    title="오류 발생 알림",
                    description=f"**```상품명이 올바르게 입력되지 않았습니다.\n\n/상품확인 명령어를 사용하여 정확한 상품명을 입력해주세요.```**"
                    )
                await interaction.send(embed=embed, ephemeral=True)
    except:
        await interaction.send('예상하지 못한 오류가 발생하였습니다.', ephemeral=True)

bot.run(TOKEN)