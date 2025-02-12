import asyncio
import hashlib
import sys

import cloudscraper
import random
from loguru import logger

KeepAliveURL = 'https://www.aeropres.in/chromeapi/dawn/v1/userreward/keepalive'
GetPointURL = "https://www.aeropres.in/api/atom/v1/userreferral/getpoint"
LoginURL = "https://www.aeropres.in/chromeapi/dawn/v1/user/login/v2"

# 初始化日志记录
logger.remove()
logger.add(sys.stdout, format='<g>{time:YYYY-MM-DD HH:mm:ss:SSS}</g> | <c>{level}</c> | <level>{message}</level>')
# logger.add(
#     "logs/file_{time}.log",  # 文件路径，会自动创建目录
#     rotation="500 MB",        # 日志文件大小达到500MB时会自动新建文件
#     encoding="utf-8",         # 设置编码
#     enqueue=True,            # 异步写入
#     retention="10 days",     # 保留10天的日志
#     format="{time:YYYY-MM-DD HH:mm:ss:SSS} | {level} | {message}",  # 文件中的日志格式
#     level="DEBUG"             # 日志级别
# )
# 三个社交绑定：
UPDATE_SOCIAL_URL = 'https://www.aeropres.in/chromeapi/dawn/v1/profile/update'
TELEGRAM_JSON = {"telegramid":"telegramid"}
DC_JSON = {"discordid":"discordid"}
X_JSON = {"twitter_x_id":"twitter_x_id"}

class ScraperReq:
    def __init__(self, proxy: dict, header: dict):
        self.scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False,
        })
        self.proxy: dict = proxy
        self.header: dict = header

    def post_req(self, url, req_json, req_param):
        # logger.info(self.header)
        # logger.info(req_json)
        return self.scraper.post(url=url, headers=self.header, json=req_json, proxies=self.proxy, params=req_param)

    async def post_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.post_req, url, req_json, req_param)

    def get_req(self, url, req_param):
        return self.scraper.get(url=url, headers=self.header, params=req_param, proxies=self.proxy)

    async def get_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.get_req, url, req_param)


async def update_social(appid, req_json, session:ScraperReq):
    id_param = {
        'appid': appid
    }
    await session.post_async(url=UPDATE_SOCIAL_URL, req_json=req_json, req_param=id_param)


async def ping(proxy_url, auth_info):
    app_id = hashlib.md5(str(random.getrandbits(128)).encode()).hexdigest()[:24]
    proxy = {
        'http': proxy_url,
        'https': proxy_url
    }
    header = {
        'content-type': 'application/json',
        'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=1, i',
        "authorization": f"Bearer {auth_info['token']}",

    }
    session = ScraperReq(proxy, header)

    try:
        res = await session.get_async(url='http://ip-api.com/json', req_param=None)
        proxy_res = res.json()['query']
        proxy_loc = res.json()['country']
    except Exception as e:
        logger.error(f"IP check failed for {auth_info['email']}: {e}")
        return

    keep_alive_request = {
        "username": auth_info['email'],
        "extensionid": "fpdkjdnhkakefebpekbdhillbhonfjjp",
        "numberoftabs": 0,
        "_v": "1.1.2"
    }
    while True:
        try:
            res = await session.post_async(url=KeepAliveURL, req_json=keep_alive_request,
                                           req_param={'appid': app_id})
            logger.info(
                f"Keep alive success: {auth_info['email']}, 代理：{auth_info['proxy']}, 代理国家：{proxy_loc}，代理ip：{proxy_res}, {res.json()['message']}")
        except Exception as e:
            logger.error(
                f"Keep alive error: {auth_info['email']}, 代理：{auth_info['proxy']}, 代理国家：{proxy_loc}，代理ip：{proxy_res} - {e}")

        try:
            req_param = {'appid': app_id}
            get_point_response = await session.get_async(
                url=GetPointURL,
                req_param=req_param
            )
            points = get_point_response.json()['data']['rewardPoint']['points']
            last_active = get_point_response.json()['data']['rewardPoint']['lastKeepAlive']
            twitter_x_id_points = get_point_response.json()['data']['rewardPoint']['twitter_x_id_points']
            discordid_points = get_point_response.json()['data']['rewardPoint']['discordid_points']
            telegramid_points = get_point_response.json()['data']['rewardPoint']['telegramid_points']

            try:
                if int(twitter_x_id_points) == 0:
                    await update_social(app_id, X_JSON, session)
                if int(discordid_points) == 0:
                    await update_social(app_id, DC_JSON, session)
                if int(telegramid_points) == 0:
                    await update_social(app_id, TELEGRAM_JSON, session)
            except Exception as e:
                pass

            logger.info(
                f"Get point success: {auth_info['email']}, 代理：{auth_info['proxy']}, 代理国家：{proxy_loc}，代理ip：{proxy_res} - 分数：{points}, 最后活跃时间：{last_active}")
        except Exception as e:
            logger.error(
                f"Get point error: {auth_info['email']}, 代理：{auth_info['proxy']}, 代理国家：{proxy_loc}，代理ip：{proxy_res} - {proxy_url} - {e}")

        await asyncio.sleep(300)  # 等待5分钟


async def process_batch(batch):
    tasks = []
    for auth in batch:
        task = asyncio.create_task(ping(auth['proxy'], auth))
        tasks.append(task)
    await asyncio.gather(*tasks)


async def main():
    # 读取账号信息
    auths = []
    with open('./dawn_files', 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if line.strip():  # 跳过空行
                email, token, proxy = line.strip().split('----')
                auth = {'email': email, 'token': token, 'proxy': proxy}
                auths.append(auth)
    total_accounts = len(auths)
    logger.info(f"Total accounts: {total_accounts}")

    # 分批处理
    await process_batch(auths)

if __name__ == "__main__":
    logger.info('🚀 [ILSH] DAWN v1.0 | Airdrop Campaign Live')
    logger.info('🌐 ILSH Community: t.me/ilsh_auto')
    logger.info('X(Twitter): https://x.com/hashlmBrian')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Program stopped by user")
    except Exception as e:
        logger.error(f"Program crashed: {e}")
