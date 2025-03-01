# -*- coding: utf-8 -*-
import re
import requests
import json
import time
import codecs
import base64
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from xml.dom import minidom
from fake_useragent import UserAgent
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_random_headers():
    ua = UserAgent()
    return {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Referer': 'https://m.tvmao.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }

def get_year():
    return datetime.now().strftime('%Y')

def get_week():
    now = datetime.now()
    week = now.strftime('%w')
    wd = int(week)
    return [str(wd)] if wd != 0 else [str(7)]

def get_time(times):
    return time.strftime("%Y%m%d%H%M%S", time.localtime(int(times)))

def get_tomorrow():
    today = datetime.today()
    return [today.strftime('%Y%m%d'), (today + timedelta(days=1)).strftime('%Y%m%d')]

def sub_req(a, q, id):
    _keyStr = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    str1 = "|" + q
    v = base64.b64encode(str1.encode('utf-8'))
    str2 = id + "|" + a
    w = base64.b64encode(str2.encode('utf-8'))
    str3 = time.strftime("%w")
    wday = 7 if int(str3) == 0 else int(str3)
    F = _keyStr[wday * wday]
    return F + str(w, 'utf-8') + str(v, 'utf-8')

def is_valid_date(strdate):
    try:
        if ":" in strdate:
            time.strptime(strdate, "%H:%M")
        else:
            return False
        return True
    except:
        return False

def saveXML(root, filename, indent="\t", newl="\n", encoding="utf-8"):
    rawText = ET.tostring(root)
    dom = minidom.parseString(rawText)
    with codecs.open(filename, 'w', 'utf-8') as f:
        dom.writexml(f, "", indent, newl, encoding)

def get_program_info(link, sublink, week_day, id_name):
    st = []
    current_year = datetime.now().year
    website = f"{link}{sublink}{week_day}.html"

    for retry in range(3):  # 添加重试机制
        try:
            r = requests.get(website, headers=get_random_headers(), timeout=10)
            r.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if retry == 2:
                logging.error(f"请求失败: {website}, 错误: {str(e)}")
                return []
            time.sleep(2 ** retry)  # 指数退避

    soup = BeautifulSoup(r.text, 'lxml')
    list_program_div = soup.find('ul', id="pgrow").find_all('div', class_="over_hide")

    for program in list_program_div:
        temp_title = program.find("span", class_="p_show")
        title = temp_title.text.strip() if temp_title else "未知节目"

        time_div = program.contents[0].text.strip()
        date_match = re.search(r'(\d{1,2}-\d{1,2})(?=\D|$)', time_div)  # 匹配日期部分
        time_match = re.search(r'(\d{1,2}:\d{2})', time_div)  # 匹配时间部分

        date_part = date_match.group(1) if date_match else '01-01'
        time_part = time_match.group(1) if time_match else '00:00'  # 如果没有时间部分，默认设为 00:00

        try:
            # 尝试解析日期和时间
            t_time = datetime.strptime(f"{current_year}-{date_part} {time_part}", '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                # 如果日期格式包含中文（如12月31日），替换为标准的日期格式
                date_part = re.sub(r'[月日]', '-', date_part).strip('-')
                t_time = datetime.strptime(f"{current_year}-{date_part} {time_part}", '%Y-%m-%d %H:%M')
            except Exception as e:
                logging.error(f"时间解析失败: {date_part} {time_part}, 错误: {str(e)}")
                t_time = datetime(current_year, 1, 1, 0, 0)  # 如果解析失败，使用默认时间

        startime = t_time.strftime("%Y%m%d%H%M%S")
        pro_dic = {"ch_title": id_name, "startime": startime, "title": title, "endtime": "000000"}
        st.append(pro_dic)

    # 处理节目时间段的逻辑
    if st:
        first_pro = st[0]
        if not first_pro['startime'].startswith(str(current_year)):
            t1 = datetime(current_year, 1, 1, 0, 0).strftime("%Y%m%d%H%M%S")
            st.insert(0, {"ch_title": id_name, "startime": t1, "title": "未知节目", "endtime": first_pro['startime']})

    for i in range(len(st) - 1):
        st[i]['endtime'] = st[i + 1]['startime']

    if st:
        last_pro = st[-1]
        end_time = datetime.strptime(last_pro['startime'], "%Y%m%d%H%M%S").replace(hour=23, minute=59, second=59)
        st[-1]['endtime'] = end_time.strftime("%Y%m%d%H%M%S")

    return st

def write_tvmao_xml(tv_channel):
    link = "https://www.tvmao.com"
    week = get_week()
    for w in week:
        for c, u in tv_channel.items():
            sublink = u[0]
            channel_id = u[1]
            try:
                # 确保 URL 拼接正确
                website = f"{link}{sublink}{w}.html"
                logging.info(f"正在处理频道: {c}, URL: {website}")
                programs = get_program_info(link, sublink, w, channel_id)
            except requests.exceptions.HTTPError as e:
                logging.error(f"请求失败：{c}，状态码：{e.response.status_code}")
                continue
            except Exception as e:
                logging.error(f"获取{c}节目表失败: {str(e)}")
                continue

            # 创建或更新频道节点
            channel_node = None
            for node in root.findall('channel'):
                if node.get('id') == channel_id:
                    channel_node = node
                    break
            if not channel_node:
                channel_node = ET.SubElement(root, 'channel', id=channel_id)
                ET.SubElement(channel_node, 'display-name', lang='zh').text = c

            # 添加节目单
            for prog in programs:
                programme = ET.SubElement(root, 'programme',
                                          start=f"{prog['startime']} +0800",
                                          stop=f"{prog['endtime']} +0800",
                                          channel=channel_id)
                ET.SubElement(programme, 'title', lang='zh').text = prog['title']

            logging.info(f"已处理频道: {c}")

tvmao_ws_dict = {
    '北京卫视': ['/program_satellite/BTV1-w', 'BTV1'],
    '卡酷少儿': ['/program_satellite/BTV10-w', 'BTV10'],
    '重庆卫视': ['/program_satellite/CCQTV1-w', 'CCQTV1'],
    '东南卫视': ['/program_satellite/FJTV2-w', 'FJTV2'],
    '厦门卫视': ['/program_satellite/XMTV5-w', 'XMTV5'],
    '甘肃卫视': ['/program_satellite/GSTV1-w', 'GSTV1'],
    '广东卫视': ['/program_satellite/GDTV1-w', 'GDTV1'],
    '深圳卫视': ['/program_satellite/SZTV1-w', 'SZTV1'],
    '南方卫视': ['/program_satellite/NANFANG2-w', 'NANFANG2'],
    '广西卫视': ['/program_satellite/GUANXI1-w', 'GUANXI1'],
    '贵州卫视': ['/program_satellite/GUIZOUTV1-w', 'GUIZOUTV1'],
    '海南卫视': ['/program_satellite/TCTC1-w', 'TCTC1'],
    '河北卫视': ['/program_satellite/HEBEI1-w', 'HEBEI1'],
    '黑龙江卫视': ['/program_satellite/HLJTV1-w', 'HLJTV1'],
    '河南卫视': ['/program_satellite/HNTV1-w', 'HNTV1'],
    '湖北卫视': ['/program_satellite/HUBEI1-w', 'HUBEI1'],
    '湖南卫视': ['/program_satellite/HUNANTV1-w', 'HUNANTV1'],
    '金鹰卡通': ['/program_satellite/HUNANTV2-w', 'HUNANTV2'],
    '江苏卫视': ['/program_satellite/JSTV1-w', 'JSTV1'],
    '江西卫视': ['/program_satellite/JXTV1-w', 'JXTV1'],
    '吉林卫视': ['/program_satellite/JILIN1-w', 'JILIN1'],
    '辽宁卫视': ['/program_satellite/LNTV1-w', 'LNTV1'],
    '内蒙古卫视': ['/program_satellite/NMGTV1-w', 'NMGTV1'],
    '宁夏卫视': ['/program_satellite/NXTV2-w', 'NXTV2'],
    '山西卫视': ['/program_satellite/SXTV1-w', 'SXTV1'],
    '山东卫视': ['/program_satellite/SDTV1-w', 'SDTV1'],
    '东方卫视': ['/program_satellite/DONGFANG1-w', 'DONGFANG1'],
    '哈哈炫动': ['/program_satellite/TOONMAX1-w', 'TOONMAX1'],
    '陕西卫视': ['/program_satellite/SHXITV1-w', 'SHXITV1'],
    '四川卫视': ['/program_satellite/SCTV1-w', 'SCTV1'],
    '康巴卫视': ['/program_satellite/KAMBA-TV-w', 'KAMBA-TV'],
    '天津卫视': ['/program_satellite/TJTV1-w', 'TJTV1'],
    '新疆卫视': ['/program_satellite/XJTV1-w', 'XJTV1'],
    '云南卫视': ['/program_satellite/YNTV1-w', 'YNTV1'],
    '浙江卫视': ['/program_satellite/ZJTV1-w', 'ZJTV1'],
    '青海卫视': ['/program_satellite/QHTV1-w', 'QHTV1'],
    '西藏卫视藏语': ['/program_satellite/XIZANGTV1-w', 'XIZANGTV1'],
    '西藏卫视': ['/program_satellite/XIZANGTV2-w', 'XIZANGTV2'],
    '延边卫视': ['/program_satellite/YANBIAN1-w', 'YANBIAN1'],
    '兵团卫视': ['/program_satellite/BINGTUAN-w', 'BINGTUAN'],
    '海峡卫视': ['/program_satellite/HXTV-w', 'HXTV'],
    '黄河卫视': ['/program_satellite/HHWS-w', 'HHWS'],
    '三沙卫视': ['/program_satellite/SANSHATV-w', 'SANSHATV']
}
tvmao_ys_dict = {
    'CCTV-1综合': ['/program/CCTV-CCTV1-w', 'CCTV1'],
    'CCTV-2财经': ['/program/CCTV-CCTV2-w', 'CCTV2'],
    'CCTV-3综艺': ['/program/CCTV-CCTV3-w', 'CCTV3'],
    'CCTV-4国际': ['/program/CCTV-CCTV4-w', 'CCTV4'],
    'CCTV-5体育': ['/program/CCTV-CCTV5-w', 'CCTV5'],
    'CCTV-5体育赛事': ['/program/CCTV-CCTV5-PLUS-w', 'CCTV5-PLUS'],
    'CCTV-6电影': ['/program/CCTV-CCTV6-w', 'CCTV6'],
    'CCTV-7国防军事': ['/program/CCTV-CCTV7-w', 'CCTV7'],
    'CCTV-8电视剧': ['/program/CCTV-CCTV8-w', 'CCTV8'],
    'CCTV-9纪录': ['/program/CCTV-CCTV9-w', 'CCTV9'],
    'CCTV-10科教': ['/program/CCTV-CCTV10-w', 'CCTV10'],
    'CCTV-11戏曲': ['/program/CCTV-CCTV11-w', 'CCTV11'],
    'CCTV-12法制': ['/program/CCTV-CCTV12-w', 'CCTV12'],
    'CCTV-13新闻': ['/program/CCTV-CCTV13-w', 'CCTV13'],
    'CCTV-14少儿': ['/program/CCTV-CCTV15-w', 'CCTV15'],
    'CCTV-15音乐': ['/program/CCTV-CCTV16-w', 'CCTV16'],
    'CCTV-16音乐': ['/program/CCTV-CCTVOLY-w', 'CCTVOLY'],
    'CCTV-17音乐': ['/program/CCTV-CCTV17NY-w', 'CCTV17NY'], 
    'CGTN西语': ['/program/CCTV-CCTV17-w', 'CCTV17'],
    'CGTN纪录': ['/program/CCTV-CCTV18-w', 'CCTV18'],
    'CGTN': ['/program/CCTV-CCTV19-w', 'CCTV19'],
    'CCTV-4欧洲': ['/program/CCTV-CCTVEUROPE-w', 'CCTVEUROPE'],
    'CCTV-4美洲': ['/program/CCTV-CCTVAMERICAS-w', 'CCTVAMERICAS'],
    'CGTN法语': ['/program/CCTV-CCTVF-w', 'CCTVF'],
    'CGTN阿语': ['/program/CCTV-CCTVA-w', 'CCTVA'],
    'CGTN俄语': ['/program/CCTV-CCTVR-w', 'CCTVR']
}
tvmao_df_dict = {
    '江西都市': ['/program/JXTV-JXTV2-w', 'JXTV2'],
    '江西经济生活': ['/program/JXTV-JXTV3-w', 'JXTV3'],
    '江西影视旅游': ['/program/JXTV-JXTV4-w', 'JXTV4'],
    '江西公共农业': ['/program/JXTV-JXTV5-w', 'JXTV5'],
    '江西少儿': ['/program/JXTV-JXTV6-w', 'JXTV6'],
    '江西新闻': ['/program/JXTV-JXTV7-w', 'JXTV7'],
    '江西移动': ['/program/JXTV-XTV8-w', 'XTV8'],
    '风尚购物': ['/program/JXTV-FSTVGO-w', 'FSTVGO'],
    '江西电视指南': ['/program/JXTV-JXTV-GUIDE-w', 'JXTV-GUIDE'],
    '江西移动': ['/program/JXTV-JXTV8-w', 'JXTV8'],
    '江西陶瓷': ['/program/JXTV-TAOCI-w', 'TAOCI'],
    '江西休闲影视':  ['/program/JXTV-JXXXYS-w', 'JXXXYS']
 }
root = ET.Element('tv')

logging.info("开始生成节目数据...")
write_tvmao_xml(tvmao_ys_dict)
write_tvmao_xml(tvmao_ws_dict)
write_tvmao_xml(tvmao_df_dict)

logging.info("保存XML文件...")
saveXML(root, "tvmao.xml")
logging.info("EPG生成完成！")