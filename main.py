import sys
import time
import traceback

import qbittorrentapi
import tldextract
import toml
from tqdm import tqdm

from utils.avalon import Avalon


def read_config() -> tuple[str, int, str, str, dict]:
    Avalon.info("读取配置文件中……", front="\n")
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
    except UnicodeEncodeError:
        with open(config_file, "r", encoding="gbk") as f:
            config = toml.load(f)
    except IOError:
        Avalon.error(f"无法加载{config_file}, 请检查文件是否存在, 文件名是否正确")
        exit(1)
    except toml.TomlDecodeError as decode_err_info:
        Avalon.error(f"载入{config_file}错误, 请检查配置文件内容是否规范无误")
        Avalon.error(decode_err_info)
        exit(1)
    except Exception:
        Avalon.error(f"无法加载{config_file}, 其他错误\n")
        Avalon.error(traceback.format_exc(3))
        exit(1)
    else:
        _host = str(config["login"]["host"])
        _port = int(config["login"]["port"])
        _username = str(config["login"]["username"])
        _passwd = str(config["login"]["password"])
        _limit_info = dict(config["upload_limit"])
        Avalon.info("配置文件读取成功")
        return _host, _port, _username, _passwd, _limit_info


def qb_login(host: str, port: int, username: str, password: str) -> qbittorrentapi.Client:
    Avalon.info("尝试登录 Web UI……", front="\n")
    # instantiate a Client using the appropriate WebUI configuration
    conn_info = dict(host=host, port=port, username=username, password=password)
    qbc = qbittorrentapi.Client(**conn_info)
    try:
        qbc.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        Avalon.error(e)
        exit(1)
    return qbc


def get_top_domain(url: str) -> str:
    extract_res = tldextract.extract(url)
    return f"{extract_res.domain}.{extract_res.suffix}"


def check_domain_match(list1, list2) -> set:
    domains1 = set(list1)  # Convert to set
    domains2 = set(list2)
    matches = domains1.intersection(domains2)
    return matches


def set_limit(torrent) -> None:
    # Get trackers
    tracker_num = torrent.trackers_count
    trackers = []
    for i in range(1, tracker_num + 1):
        trackers.append(torrent.trackers[-i]["url"])
    trackers = [get_top_domain(url) for url in trackers]  # conv to top domain

    # Check if the torrent's tracker in our config
    matches = check_domain_match(trackers, limit_info.keys())
    if not matches:
        return None  # No need to set the limit

    # Get target limit
    target_limit = min(list(map(limit_info.get, matches)))  # Get the min value if multi tracker

    # Set upload_limit
    target_limit_conv = int(target_limit * 1024 * 1024)  # MB/s to Byte/s
    if torrent.upload_limit == 0 or target_limit_conv != torrent.upload_limit:
        torrent.set_upload_limit(target_limit_conv)
        Avalon.info(f"已限制 {torrent.name} | {torrent.hash[-12:]} | {trackers[0]} | 上传为 {target_limit} MB/s.")


if __name__ == '__main__':
    host, port, username, passwd, limit_info = read_config()
    qbt_client = qb_login(host, port, username, passwd)
    Avalon.info(f"qBittorrent: {qbt_client.app.version}")
    Avalon.info(f"qBittorrent Web API: {qbt_client.app.web_api_version}")

    torrents = qbt_client.torrents.info()
    Avalon.info(f"读取到的种子数为：{len(torrents)}, 开始处理...")
    for torrent in tqdm(torrents):
        set_limit(torrent)
        time.sleep(0.01)

    Avalon.info("执行完毕", front="\n")
    qbt_client.auth_log_out()
