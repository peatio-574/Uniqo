import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import json
import time
import random
import requests
import re

from lgb import ESP32Controller
import os
from PlayWright import Playwright_, get_config_value, write_config_value, logger
import pandas
from openpyxl.styles import Font

eleInfo = {
    '返回': [0.08304, 0.06057],
    '0': [0.49786, 0.94586],
    '1': [0.18026, 0.73347],
    '2': [0.50434, 0.73149],
    '3': [0.81977, 0.73943],
    '4': [0.17378, 0.80493],
    '5': [0.51082, 0.79997],
    '6': [0.82193, 0.80493],
    '7': [0.18026, 0.86746],
    '8': [0.51082, 0.87440],
    '9': [0.83490, 0.87143]
}

configFile = os.path.join(os.path.dirname(__file__), 'config.ini')

orderColors = {
    '白色': 'https://img.alicdn.com/imgextra/i2/O1CN01k51piZ1htTu279fNe_!!6000000004335-2-tps-120-120.png?getAvatar=avatar',
    '紫色': 'https://img.alicdn.com/imgextra/i3/O1CN01cXPJrS1BzNIMCmPdu_!!6000000000016-2-tps-120-120.png?getAvatar=avatar',
    '红色': 'https://img.alicdn.com/imgextra/i4/O1CN015SWzPn1ZYOkHKAWft_!!6000000003206-2-tps-120-120.png?getAvatar=avatar',
}

baseHeaders = {
    'user-agent': get_config_value('login', 'user-agent'),
    'content-type': 'application/json',
}

def uniqloLogin():
    """优衣库登录"""
    # 验证优衣库cookie有效性
    addUniqloCookie()
    url = 'https://www.uniqlo.cn/account/person_ship_code.html'
    location = '//div[contains(text(),"会员码")]'
    Playwright_.goto(url)
    time.sleep(5)
    element = Playwright_.wait_for_selector(location, timeout=3 * 60 * 1000)
    if not element:
        logger.info('❌️ 优衣库登录失败')
        return False

    uniqloCookie = Playwright_.context.cookies()
    uniqloCookieApi = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in uniqloCookie])
    for cookie in uniqloCookie:
        if cookie.get("name") == 'access_token':
            reuslt = {'uniqloToken': cookie["value"], 'uniqloCookie': str(uniqloCookie), 'uniqloCookieApi': uniqloCookieApi}
            write_config_value('uniqlo', reuslt)  # token写入ini配置项
            getPhone()
    logger.info('✅ 优衣库登录成功')
    return True

def orderLogin():
    """登录千牛"""
    url = 'https://myseller.taobao.com/home.htm/QnworkbenchHome/'
    ele = '//span[contains(text(),"首页")]'
    key = 'alibaba.orderCookie'
    loginStatus = Playwright_.login(url, ele, key, file=configFile)
    if loginStatus:
        logger.info('✅ 千牛登录成功')
    else:
        logger.error('❌️ 千牛登录失败')
    return loginStatus

def addOrderCookie():
    """页面添加千牛cookie"""
    orderCookie = get_config_value('alibaba', 'orderCookie', file=configFile)
    if orderCookie:
        Playwright_.add_cookie(eval(orderCookie))

def addUniqloCookie():
    """页面添加优衣库cookie"""
    uniqloCookie = get_config_value('uniqo', 'uniqloCookie', file=configFile)
    if uniqloCookie:
        Playwright_.add_cookie(eval(uniqloCookie))

def getOrderCodes(flag='紫色'):
    """
    获取指定旗帜类型的所有订单号，默认为紫色
    返回形式：list（按日期排序）
    """
    # 加入cookie
    addOrderCookie()
    # 访问页面
    Playwright_.goto('https://qn.taobao.com/home.htm/trade-platform/tp/sold')
    result = Playwright_.wait_for_selector('//input[@aria-label="搜索"]', timeout=15*1000)
    if not result:  # 搜索按钮未加载出来
        return False
    time.sleep(5)

    switch_ele = '//div[@class="driver-popover"]//button[@class="driver-popover-next-btn"]'
    switch_count = Playwright_.get_count(switch_ele)
    if switch_count:
        Playwright_.click(switch_ele)
        time.sleep(3)

    # 点击待发货
    Playwright_.click('//div[@class="next-tabs-tab-inner" and contains(text(), "待发货")]')
    orders = dict()
    time.sleep(5)
    pages = int(Playwright_.get_text('//div[@class="next-pagination-list"]/button[last()]/span'))  # 页数
    for page in range(1, pages+1):
        # 单页订单量
        rowEle = '//table[contains(@class, "next-table-row")]'
        rowCount = Playwright_.get_count(rowEle)
        for rowId in range(1, rowCount+1):
            orderCodeEle = f'({rowEle})[{rowId}]//div[contains(text()[1], "订单号")]'  # 订单号
            orderCode = Playwright_.get_text(orderCodeEle)
            orderCode = re.findall(r'\d+', orderCode)[0]  # 订单号

            orderColorEle = f'({rowEle})[{rowId}]//img[contains(@class,"sold_new")]'  # 旗帜颜色
            colorSrc = Playwright_.get_attribute(orderColorEle, 'src')
            if orderColors[flag] != colorSrc:  # 旗帜颜色不匹配
                continue

            orderDateEle = f'({rowEle})[{rowId}]//span[contains(@class,"sold_create-time")]'  # 订单日期
            orderDate = Playwright_.get_text(orderDateEle)
            orderDate = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', orderDate)[0]
            orders[orderCode] = orderDate

        if pages == 1 or page == pages:
            break
        Playwright_.page.keyboard.press("End")  # 滚动
        Playwright_.click('//span[text()="下一页"]')  # 页码跳转
        time.sleep(5)
    realOrders = sorted(orders.items(), key=lambda x: x[1])  # 根据日期排序
    orderCodes = [i[0] for i in realOrders]
    return orderCodes

def displayOrderInfo():
    """将千牛订单信息从隐藏状态改为显示状态"""
    addrEle = '//span[@class="receive-address_value__Fmomy"]'
    addr = Playwright_.get_text(addrEle)
    for roll in range(3):
        if '*****' not in addr:
            break
        logger.info('订单信息已隐藏，尝试点击展开获取订单信息')
        Playwright_.click('//div[@role="switch"]/div[2]')
        time.sleep(2)
        addr = Playwright_.get_text(addrEle)
    return addr

def getOrderDetail(orderCode, isWrite=False):
    """
    获取指定订单的订单详情
    isWrite是否进行订单信息写入
    返回：[{'title': '', 'product': '', 'colorCode': '', 'color': '', 'size': '', 'quantity': '', 'addr': ''}, {}]
    """
    addOrderCookie()
    url = f'https://qn.taobao.com/home.htm/trade-platform/tp/detail?spm=a21dvs.23580594.0.0.60fb645eXEF8jc&bizOrderId={orderCode}'
    Playwright_.goto(url)
    time.sleep(3)

    orderInfo = []

    addr = displayOrderInfo()
    if '*****' in addr:
        logger.info(f'订单信息仍为隐藏状态，跳过该订单：{orderCode}：{addr}')
        return orderInfo

    logger.info(f'{orderCode}订单地址：{addr}')

    subOrderEle = '//tr[@class="order-item"]'
    subOrderCount = Playwright_.get_count(subOrderEle)

    for subOrderId in range(1, subOrderCount + 1):
        # 标题
        productTitleEle = f'({subOrderEle})[{subOrderId}]//div[contains(@class, "first-right-title")]/a'
        productTitle = Playwright_.get_text(productTitleEle)

        # 商品状态（未发货、已退款、待收货）
        subOrderStatusEleOne = f'({subOrderEle})[{subOrderId}]/td[3]/div[1]/span'
        subOrderStatusEleTwo = f'({subOrderEle})[{subOrderId}]/td[3]/div[1]/a'
        subOrderStatus = ''
        if Playwright_.get_count(subOrderStatusEleOne):
            subOrderStatus = Playwright_.get_text(subOrderStatusEleOne)
        elif Playwright_.get_count(subOrderStatusEleTwo):
            subOrderStatus = Playwright_.get_text(subOrderStatusEleTwo)
        if '收货' in subOrderStatus:
            logger.info(f"{orderCode} {productTitle}   已发货，暂不计入订单\n")
            continue
        elif '退款' in subOrderStatus:
            logger.info(f"{orderCode} {productTitle}   已退款，暂不计入订单\n")
            continue

        # 商品编号
        productCodes = re.findall(r'\d{6}', productTitle)
        productCodes = list(set(productCodes))
        if not productCodes:
            logger.info(f"{orderCode} {productTitle}   商品编号异常，暂不计入订单：{productTitle}")
            continue

        # 商品颜色编号
        colorEle = f'({subOrderEle})[{subOrderId}]//span[contains(text(),"颜色")]/../span[2]/span'
        colorString = Playwright_.get_text(colorEle)
        colorCode = re.findall(r'\[(\d+)', colorString)
        if not colorCode:
            logger.info(f"{orderCode} {productTitle}   颜色编号异常，暂不计入订单：{colorString}")
            continue
        colorCode = colorCode[0]
        # 商品颜色
        color = re.findall(r'[\u4e00-\u9fa5]+', colorString)[0]

        # 商品尺寸
        sizeEle = f'({subOrderEle})[{subOrderId}]//span[contains(text(),"尺")]/../span[2]/span'
        size = Playwright_.get_text(sizeEle)

        # 商品数量
        quantityEle = f'({subOrderEle})[{subOrderId}]//div[contains(@class, "total-price")]/div[2]'
        quantity = Playwright_.get_text(quantityEle)[1:]

        # 商品价格
        priceEle = f'({subOrderEle})[{subOrderId}]//div[contains(@class, "total-price")]/div[1]'
        price = Playwright_.get_text(priceEle)

        subOrderInfo = {
            'productTitle': productTitle,
            'productCodes': productCodes,
            'colorCode': colorCode,
            'color': color,
            'size': size,
            'quantity': int(quantity),
            'price': price,
            'addr': addr,
            'fullTitle': f'【订单：{orderCode}】{productTitle}\t\t颜色：{colorCode}{color}\t\t尺寸：{size}'
        }
        orderInfo.append(subOrderInfo)
    if isWrite:
        file = os.path.join(os.path.dirname(__file__), '订单信息.txt')
        with open(file, mode='a', encoding='utf-8') as f:
            tmpInfo = {orderCode: orderInfo}
            f.write(f'{tmpInfo}\n')
    return orderInfo

def getUniqloCodes(productCode, colorCode, color, match=True):
    """
    根据千牛的productCode/color/colorCode获取优衣库对应uniqloCode
    match是否严格匹配商品货号productCode一致
    返回：[]
    """
    url = 'https://d.uniqlo.cn/p/hmall-sc-service/search/searchWithDescriptionAndConditions/zh_CN'

    params = {
        "url": f"/search.html?description={productCode}&searchType=4",
        "pageInfo": {
            "page": 1,
            "pageSize": 20,
            "withSideBar": "Y"
        },
        "belongTo": "pc",
        "rank": "overall",
        "priceRange": {
            "low": 0,
            "high": 0
        },
        "color": [],
        "size": [],
        "season": [],
        "material": [],
        "sex": [],
        "categoryFilter": {},
        "identity": [],
        "insiteDescription": "",
        "exist": [],
        "searchFlag": True,
        "description": str(productCode)
    }
    info = requests.post(url, headers=baseHeaders, data=json.dumps(params)).json()
    uniqloCodes = []
    for product in info['resp'][1]:  # 多个结果
        if match:  # 严格匹配商品货号
            if product.get('code') and product.get('code') != str(productCode):  # 商品编号不一致
                continue
        styles = product['styleText']  # 颜色型号
        if isinstance(styles, str):  # 字符串类型
            if f'{colorCode}{color}' in styles.replace(' ', ''):
                uniqloCode = product['productCode']
                uniqloCodes.append(uniqloCode)
        elif isinstance(styles, list):  # 列表类型
            for style in styles:
                if f'{colorCode}{color}' in style.replace(' ', ''):
                    uniqloCode = product['productCode']
                    uniqloCodes.append(uniqloCode)
    return uniqloCodes

def dealSize(size):
    if size == '2XL':
        size = [size, 'XXL']
    elif size == '3XL':
        size = [size, 'XXXL']
    elif size == '4XL':
        size = [size, 'XXXXL']
    elif size == '1XL':
        size = 'XL'
    else:
        size = str(size)
    return size

def getUniqloSizeCode(productCode, uniqloCode, colorCode, color, size):
    """根据productCode、uniqloCode、colorCode、size获取uniqloSizeCode
    uniqloCode为优衣库获取
    productCode、colorCode、size为千牛获取
    """
    addUniqloCookie()
    url = f'https://www.uniqlo.cn/data/products/spu/zh_CN/{uniqloCode}.json'
    Playwright_.goto(url)
    time.sleep(2)
    info = Playwright_.get_text('//pre')
    info = json.loads(info)['rows']
    newSize = dealSize(size)

    for sku in info:
        if sku.get('enabledFlag') == 'N':  # 不可售
            continue
        if productCode not in sku['name'] or uniqloCode != sku['productCode']:  # 商品编号不匹配
            continue
        if f'{colorCode}{color}' in sku['styleText'].replace(' ', ''):  #  颜色匹配
            if isinstance(newSize, str):  # 尺寸匹配 str
                if sku['size'].replace(' ', '') == newSize:
                    uniqloSizeCode = sku['productId']
                    return uniqloSizeCode
            elif isinstance(newSize, list): # 尺寸匹配 list
                if sku['size'].replace(' ', '') in newSize:
                    uniqloSizeCode = sku['productId']
                    return uniqloSizeCode
    return ''

def uniqloWalk():
    """
    优衣库闲逛，为了减少账号风控，在网页上进行闲逛浏览
    返回：闲逛时长int
    """
    t1 = time.time()
    addUniqloCookie()
    url = 'https://www.uniqlo.cn/c/2wouter.html'
    Playwright_.goto(url)
    choose = ['休闲外套', '大衣', '空气感快干外套', '西装外套', '空气棉服', '羽绒服']
    for i in range(4):
        Playwright_.goto(url)
        Playwright_.click(f'//a[@class="h-a-label a-enable" and text()="{random.choice(choose)}"]')
        time.sleep(random.randint(5, 10))
        Playwright_.click('(//div[@class="product-background"])[1]')
        Playwright_.page.mouse.wheel(0, 1200)  # 滚动
        time.sleep(random.randint(10, 30))
    t2 = time.time()
    return int(t2-t1)

def getuniqloCount(uniqloCode, uniqloSizeCode):
    """
    根据uniqloCode，uniqloSizeCode获取商品库存
    返回：int
    """
    url3 = 'https://d.uniqlo.cn/p/stock/stock/query/zh_CN'
    params = {
        "distribution": "EXPRESS",
        "productCode": uniqloCode,
        "type": "DETAIL"
    }
    info = requests.post(url3, headers=baseHeaders, data=json.dumps(params)).json()
    uniqloCount = info['resp'][0]['skuStocks'].get(uniqloSizeCode)
    uniqloCount = int(uniqloCount)
    return uniqloCount

def uniqloHeaders(flag=False):
    """优衣库接口headers"""
    headers = {
        'user-agent': get_config_value('login', 'user-agent'),
        'authorization': 'bearer ' + get_config_value('uniqlo', 'uniqloToken', file=configFile),
        'cookie': get_config_value('uniqlo', 'uniqloCookieApi', file=configFile)
    }
    if flag:
        headers['content-type'] = 'application/json'
    return headers

def getAddrList():
    """获取地址列表"""
    url = 'https://i.uniqlo.cn/p/hmall-ur-service/v2/customer/address/list'
    response = requests.get(url, headers=uniqloHeaders()).json()
    tmp = response.get('resp')
    addrList = [i['addressId'] for i in tmp] if tmp else []
    return addrList

def deleteAddr(addrCode):
    """删除单个地址"""
    url = f'https://i.uniqlo.cn/p/hmall-ur-service/customer/address/delete/{addrCode}/zh_CN'
    requests.post(url, headers=uniqloHeaders(flag=True)).json()
    return True

def dealAddrStr(addrStr):
    """处理千牛获取到的地址，用于优衣库地址新增
    addrStr： '杨智斌，14735147458-8192，山西省 太原市 杏花岭区 职工新街街道 东方雅园2号楼1单元801 ，030009'
    返回list：[provinceName, cityName, districtName, address, mobilenumber, consignee]
    """
    add_str = addrStr.split('，')
    # 地址
    address = ''.join([i for i in add_str[2].split(' ')])
    address = ''.join([char if char.isalnum() or '\u4e00' <= char <= '\u9fa5' else '' for char in address])
    address = address if '86-' in add_str[1] else address + ' 电话转' + add_str[1].split('-')[1]
    # 电话
    mobilenumber = re.findall(r'1[3-9]\d{9}', add_str[1])[0]
    # 姓名
    consignee = add_str[0]
    # 省份
    provinceName = add_str[2].split(' ')[0]
    # 城市
    cityName = add_str[2].split(' ')[1]
    # 区县
    districtName = add_str[2].split(' ')[2]
    return [provinceName, cityName, districtName, address, mobilenumber, consignee]

def addAddr(addrStr):
    """新增地址，并返回对应addr_id
    addrStr：从千牛获取 '杨智斌，14735147458-8192，山西省 太原市 杏花岭区 职工新街街道 东方雅园2号楼1单元801 ，030009'
    返回addrCode
    """
    provinceName, cityName, districtName, address, mobilenumber, consignee = dealAddrStr(addrStr)
    uniqloLogin()
    time.sleep(random.randint(5, 10))
    Playwright_.goto('https://www.uniqlo.cn/account/address.html')
    Playwright_.click('//button[text()="新增收货地址"]')
    Playwright_.click('(//i[@class="icon "])[1]')
    Playwright_.click(f'//li[contains(text(),"{provinceName}")]')
    Playwright_.click('(//i[@class="icon "])[2]')
    Playwright_.click(f'//li[contains(text(),"{cityName}")]')
    Playwright_.page.locator('//input[@name="consignee"]').fill(consignee)
    Playwright_.page.locator('//input[@name="address"]').fill(address)
    Playwright_.page.locator('//input[@name="mobilenumber"]').fill(mobilenumber)
    Playwright_.click('//button[@type="submit"]')
    Playwright_.click('//button[text()="确认"]')
    time.sleep(random.randint(2, 4))
    validAddrEle = '//label[text()="收货地址："]/../span'
    validAddrCount = Playwright_.get_count(validAddrEle)
    validAddr = [Playwright_.get_text(f'({validAddrEle})[{i}]') for i in range(1, validAddrCount+1)]
    return True if address[:15] in str(validAddr) else False

def getPurchaseList():
    """获取购物车列表"""
    url = 'https://i.uniqlo.cn/p/cart/cart/query/pc/zh_CN?salechannel=PC'
    response = requests.get(url, headers=uniqloHeaders()).json()
    info = response.get('resp')
    purchaseList = [i['cartId'] for i in info if '未上架' not in i['msg']] if info else []
    return purchaseList

def detelePurchaseList(purchaseList):
    """清空购物车列表"""
    if not purchaseList:
        return True
    url = 'https://i.uniqlo.cn/p/cart/cart/multDelete/zh_CN'
    params = {"select": purchaseList}
    requests.post(url, headers=uniqloHeaders(flag=True), data=json.dumps(params)).json()
    return True

def addToPurchase(uniqloCode, uniqloSizeCode, quantity):
    """加入购物车"""
    url = 'https://i.uniqlo.cn/p/cart/cart/insert/zh_CN'
    params = [
        {
            "productCode": uniqloCode,
            "productId": uniqloSizeCode,
            "quantity": quantity,
            "distribution": "EXPRESS",
            "distributionId": "",
            "alterMode": "",
            "finalInseam": None,
            "caseFlag": "N",
            "checkFlag": "Y"
        }
    ]
    requests.post(url, headers=uniqloHeaders(), data=json.dumps(params)).json()
    return True

def getPhone():
    """获取优衣库手机号"""
    url = 'https://i.uniqlo.cn/h/auth/user/zh_CN'
    result = requests.get(url, headers=uniqloHeaders()).json()['mobileNumber']
    write_config_value('login', {'phone': result})
    return result

def checkRobotStatus():
    logger.info('开始扫描机械设备')
    controller = ESP32Controller()
    devices = ESP32Controller.scan_lan()
    if len(devices) == 0:
        return False
    logger.info(f"发现机械设备: {devices}")
    return controller, devices[0]

def modifyOrderStatus(orderCode, text=None):
    """修改紫旗、蓝旗状态"""
    orderLogin()
    # 访问页面
    Playwright_.goto('https://qn.taobao.com/home.htm/trade-platform/tp/sold')
    Playwright_.wait_for_selector('//input[@aria-label="搜索"]')
    time.sleep(10)
    # 输入order_id
    Playwright_.input('//input[@aria-label="搜索"]', str(orderCode))
    # 点击搜索订单
    Playwright_.click('//span[text()="搜索订单"]')
    time.sleep(5)

    # 点击编辑
    Playwright_.page.evaluate("window.scrollBy(0, 400)")  # 滚动
    Playwright_.click(f'//div[contains(text()[2], "{orderCode}")]/../div[2]/div')

    # 点击旗帜颜色
    if text:
        Playwright_.click('(//span[text()="添加标签"])[1]/../../label/span//input')
        # 添加备注
        Playwright_.input('//textarea', text)
    else:
        Playwright_.click('(//span[text()="添加标签"])[5]/../../label/span//input')
    # 点击确定
    Playwright_.click('//span[text()="取消"]/../../button[1]/span')
    return text if text else True

def clear():
    """清除cookie"""
    logger.info('开始清除千牛登录信息')
    write_config_value('alibaba', {'orderCookie': ''}, file=configFile)
    logger.info('开始清除优衣库登录信息')
    write_config_value('uniqlo', {'uniqloCookie': '', 'uniqloCookieApi': '', 'uniqloToken': ''}, file=configFile)
    logger.info('清除登录信息成功')

def uniqloSubmit():
    """优衣库提交订单"""
    Playwright_.goto('https://www.uniqlo.cn/cart.html')
    time.sleep(3)
    Playwright_.click('//button[text()="立即结算"]')
    Playwright_.click('//button[text()="提交订单"]')

def addSpecialProduct(uniqloCode='u0000000074588', uniqloSizeCode='u0000000074588025', quantity=1):
    """优衣库凑单"""
    addToPurchase(uniqloCode, uniqloSizeCode, quantity)

def deleteSpecialProduct(uniqloOrderCode, productCode='486121'):
    """删除优衣库凑单商品"""
    list_url = 'https://www.uniqlo.cn/account/order/order_list.html'
    Playwright_.goto(list_url)
    time.sleep(3)
    refund_ele = f'//tr[@id="{uniqloOrderCode}"]/following-sibling::tr//a[contains(text(), "{productCode}")]/../../..//a[text()="申请退款"]'
    Playwright_.click(refund_ele)
    Playwright_.click('//div[text()="请选择"]')
    Playwright_.click('//li[text()="拍错了/订单信息有误"]')
    Playwright_.input('//textarea', '拍错了')
    Playwright_.click('//button[text()="提交申请"]')

def executeSingleOrder(orderCode, resultMany, isWrite=True):
    """单次单个订单"""
    orderInfo = getOrderDetail(orderCode, isWrite=isWrite)
    logger.info(f'开始处理{orderCode}订单：{[i["productTitle"] for i in orderInfo]}')
    if not orderInfo:
        logger.info(f'{orderCode}无匹配订单数据，无需处理')
        return None

    # 清空购物车
    logger.info('清空购物车....')
    purchaseList = getPurchaseList()
    detelePurchaseList(purchaseList)

    # 删除地址
    logger.info('删除快递地址....')
    addrList = getAddrList()
    for addrCode in addrList:
        deleteAddr(addrCode)

    successSubOrder = []
    for subOrder in orderInfo:
        logger.info(f'开始处理子订单：{subOrder}')
        fullTitle = subOrder['fullTitle']
        size = subOrder['size']
        quantity = subOrder['quantity']
        color = subOrder['color']
        colorCode = subOrder['colorCode']
        addr = subOrder['addr']
        productCodes = subOrder['productCodes']
        if len(productCodes) > 1:
            logger.info(f'{fullTitle}\t\t存在多个{productCodes}')
        currentSubOrder = []
        for productCode in productCodes:
            # 多个uniqloCode
            logger.info(f'开始处理：{productCode}')
            uniqloCodes = getUniqloCodes(productCode, colorCode, color, match=resultMany)
            logger.info(f'千牛商品编号：{productCode}匹配的优衣库商品编号：{uniqloCodes}')
            for uniqloCode in uniqloCodes:
                # 获取uniqloSizeCode
                uniqloSizeCode = getUniqloSizeCode(productCode, uniqloCode, colorCode, color, size)
                logger.info(
                    f'千牛商品编号：{productCode}、优衣库商品编号：{uniqloCode}匹配的优衣库商品尺寸编号：{uniqloSizeCode}')
                # 获取uniqloCount
                uniqloCount = getuniqloCount(uniqloCode, uniqloSizeCode)
                logger.info(f'颜色编号：{colorCode}、颜色：{color}、尺寸：{size}匹配的优衣库商品库存：{uniqloCount}')
                # 判断库存
                if uniqloCount < quantity:
                    logger.info(f'{fullTitle}\t\t库存不足，千牛下单数量：{quantity}，优衣库库存：{uniqloCount}，跳过子订单')
                    continue
                # 添加购物车
                addToPurchase(uniqloCode, uniqloSizeCode, quantity)
                logger.info(f'{productCode}添加购物车成功')
                successSubOrder.append(subOrder)
                currentSubOrder.append(productCode)
                break
            if not resultMany or currentSubOrder:
                break
    return successSubOrder

def onceRunRobot(controller, deviceIp, resultMany, isShip):
    """start首次运行为False，后续为True"""
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    content = now + '电商订单自动下单'
    logger.info(content.center(100, '='))

    logger.info('开始千牛登录....')
    login = orderLogin()
    if not login:
        return False

    logger.info('开始优衣库登录....')
    login = uniqloLogin()
    if not login:
        return False

    logger.info('获取千牛订单....')
    orderCodes = getOrderCodes(flag='紫色')
    logger.info(f'千牛订单：{orderCodes}')
    if len(orderCodes) == 0:
        logger.info('暂无需要处理订单')
        return False

    logger.info('获取千牛每个订单详情....')
    for orderCode in orderCodes:
        # 执行单个订单
        successSubOrder = executeSingleOrder(orderCode, resultMany, isWrite=True)

        if not successSubOrder:
            logger.info(f'{orderCode}无匹配订单数据，跳过该订单')
            continue

        # 添加地址
        addr = successSubOrder[0]['addr']
        logger.info(f'开始添加快递地址：{addr}')
        isAddAddr = addAddr(addr)

        if not isAddAddr:
            logger.info(f'{orderCode}添加快递地址失败，跳过该订单')
            continue

        if isShip == '0':
            addSpecialProduct()
            logger.info('凑单商品添加购物车成功')
        uniqloSubmit()
        # 支付
        startTime = time.time()
        status = pay(controller, deviceIp)
        if not status:
            logger.error(f'{orderCode}订单支付失败！！！')
            continue
        endTime = time.time()
        uniqloOrderCode = getUniqloOrderCode(startTime, endTime)
        if not uniqloOrderCode:
            logger.error(f'{orderCode}订单未找到对应优衣库购买编号！！！')
            logger.error(f'{orderCode}订单未找到对应优衣库购买编号！！！')
            logger.error(f'{orderCode}订单未找到对应优衣库购买编号！！！')
            continue
        logger.info(f'{orderCode}订单对应优衣库购买编号为{uniqloOrderCode}')
        deleteSpecialProduct(uniqloOrderCode)
        # 备注
        tel = get_config_value('login', 'phone')[:3]
        date = get_config_value('login', 'date')
        text = f'总仓发{tel}【{date}】' if successSubOrder == orderInfo else [i['productTitle'] for i in successSubOrder]
        expect_text = modifyOrderStatus(orderCode, text)
        logger.info(f'{orderCode}订单已修改旗帜为红色，并添加备注信息：{expect_text}')
    return True

def getUniqloOrderCode(startTime, endTime):
    """根据时间戳，获取优衣库购买订单编号"""
    uniqloLogin()
    startTime = startTime * 1000
    endTime = endTime * 1000
    url = 'https://i.uniqlo.cn/p/hmall-od-service/order/queryForUserOrders/1/10/zh_CN'
    params = {}
    response = requests.post(url, headers=uniqloHeaders(flag=True), data=json.dumps(params)).json()['resp'][0]
    if startTime <= response['creationTime'] <= endTime and response['status'] == 'WAIT_SHIP':
        return response["orderId"]
    return None

def pay(controller, device_ip, server='127.0.0.1', rotation=3):
    """支付宝支付"""
    global eleInfo
    logger.info('优衣库APP操作')
    if not eleInfo.get('首次'):
        logger.info('点击会员')
        controller.ocr_text_and_click(server, device_ip, rotation, '会员', home=False)
        logger.info('点击所有订单')
        controller.ocr_text_and_click(server, device_ip, rotation, '所有订单', home=False)
        eleInfo['首次'] = True
    else:
        logger.info('点击返回')
        controller.move_click(device_ip=device_ip, x_ratio=eleInfo['返回'][0], y_ratio=eleInfo['返回'][1], home=False)

    logger.info('点击立即支付')
    controller.ocr_text_and_click(server, device_ip, rotation, '立即支付', home=False)
    logger.info('点击支付宝')
    tmp_location = controller.ocr_get_text_location(server, device_ip, rotation, '支付宝', home=True)
    controller.move_click(device_ip=device_ip, x_ratio=tmp_location[0]+0.2, y_ratio=tmp_location[1], home=True)
    logger.info('点击确认支付')
    controller.ocr_text_and_click(server, device_ip, rotation, '确认支付', home=False)
    time.sleep(3)
    logger.info('输入支付密码...')
    password = str(get_config_value('login', 'password'))
    for word in password:
        controller.move_click(device_ip=device_ip, x_ratio=eleInfo[word][0], y_ratio=eleInfo[word][1], home=True)

    write_config_value('login', {'date': time.strftime("%m-%d %H:%M", time.localtime())})

    time.sleep(3)
    logger.info('点击完成')
    controller.ocr_text_and_click(server, device_ip, rotation, '完成', home=False)
    return True

def runRobot():
    """运行机械臂下单"""
    isShip = input("请选择是否包邮（1是、0否）：")
    resultMany = input("请输入是否支持查询多个产品（1是、0否）：")
    resultMany = True if resultMany == '1' else False

    number = int(get_config_value('login', 'number'))
    interval = int(get_config_value('login', 'interval'))

    controller, deviceIp = checkRobotStatus()

    for i in range(number):
        onceRunRobot(controller, deviceIp, resultMany, isShip)
        logger.info(f'等待{interval}秒再次执行')
        keepTime = uniqloWalk() + uniqloWalk() + uniqloWalk()
        time.sleep(interval - keepTime)

class Uniqlo(object):
    infos = {}

    @classmethod
    def getPageInfo(cls, page=1):
        """获取每页数据"，返回总数和当页数据"""
        url = f'https://i.uniqlo.cn/p/hmall-od-service/order/queryForUserOrders/{page}/10/zh_CN'
        logger.info(f'查询第{page}页订单数据')
        response = requests.post(url, headers=uniqloHeaders(), json={}).json()
        logger.info(response)
        return response['total'], response['resp']

    @classmethod
    def dealPageInfo(cls, pageInfo):
        """处理每页数据"""
        for orderInfo in pageInfo:  # 每条订单
            for subOrder in orderInfo['details']:  # 订单的每条数据
                status = subOrder['status']
                if status in ['CANCELLED', 'CLOSED']:  # 无效订单
                    continue
                # good_no = order['summaryInfo']['code']
                color = subOrder['productDetailInfo']['styleText'].replace(' ', '')
                goodsNo = re.findall(r'\d{6}', color)[0] if re.findall(r'\d{6}', color) else subOrder['summaryInfo'][
                    'code']
                color = re.findall(r'\d+[\u4e00-\u9fff]+', color)[0] if '色' in color else color
                size = subOrder['productDetailInfo']['sizeText']
                price = '价格：' + subOrder['productDetailInfo']['price']

                if size == 'XXL':
                    size = '2XL'
                elif size == 'XXXL':
                    size = '3XL'
                elif size == 'XXXXL':
                    size = '4XL'

                if not cls.infos.get(goodsNo):
                    cls.infos[goodsNo] = dict()
                if not cls.infos.get(good_no).get(color):
                    cls.infos[goodsNo][color] = dict()
                if not cls.infos.get(good_no).get(color).get(size):
                    cls.infos[goodsNo][color][size] = {}

                if not cls.infos.get(good_no).get(color).get(size).get(price):
                    cls.infos[goodsNo][color][size][price] = subOrder['quantity']
                else:
                    cls.infos[goodsNo][color][size][price] += subOrder['quantity']
        return True

    @classmethod
    def getPagesInfo(cls):
        """获取所有页订单数据"""
        uniqloLogin()
        total, pageInfo = cls.getPageInfo(1)
        cls.dealPageInfo(pageInfo)
        pages = total // 10 if total % 10 == 0 else total // 10 + 1
        for page in range(2, pages + 1):
            pageInfo = cls.getPageInfo(page)[1]
            cls.dealPageInfo(pageInfo)
            
    @classmethod
    def xlsxAppend(cls, data, filename):
        try:
            pd = pandas.DataFrame(data)
            with pandas.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                workbook = writer.book
                sheet = workbook.active
                startRow = sheet.max_row
                pd.to_excel(writer, sheet_name='Sheet1', startrow=startRow, index=False, header=True)
                cols = pd.shape[1]  # 列数
                for col in range(1, cols + 1):
                    sheet.cell(row=startRow + 1, column=col).font = Font(bold=True)
            logger.info('数据写入成功')
            return True
        except Exception as e:
            logger.error('数据写入失败：%s' % e)
            return False

    @classmethod
    def queryUniqloOrder(cls):
        """查询优衣库订单信息"""
        date = time.strftime('%Y-%m-%d %H:%M:%S')
        filename = os.path.join(os.path.dirname(__file__), '优衣库订单统计表.xlsx')

        logger.info('开始获取优衣库订单数据.....')
        cls.getPagesInfo()
        time.sleep(2)
        phone = getPhone()

        while True:
            text = input('请输入查询货号（附带查询价格时请用逗号隔开，如：482295 99）：')
            if text == '1':
                exit()
            text = text.split(' ')
            goodsNo = text[0]
            currentInfo = cls.infos.get(goodsNo)
            if currentInfo is None:
                logger.info(f'当前货号：{goodsNo}暂无数据')
                continue
            if len(text) == 1:
                currentInfo = {k: {a: sum(list(b.values())) for a, b in v.items()} for k, v in currentInfo.items()}
            elif len(text) == 2:
                currentInfo = {k: {a: b[f'价格：{text[1]}'] for a, b in v.items() if f'价格：{text[1]}' in b.keys()} for
                                k, v in currentInfo.items()}

            if not currentInfo:
                logger.info(f'{goodsNo}货号暂无数据！！！')
                continue

            logger.info(f'{goodsNo}货号数据为：{currentInfo}')

            allSize = list()  # 当前商品的全部尺寸
            for v in currentInfo.values():
                for key in v.keys():
                    if key not in allSize:
                        allSize.append(key)

            tmpSize = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL', '6XL']
            isSize = False
            for i in allSize:
                if i in tmpSize:
                    isSize = True
                    break
            allSize = sorted(allSize) if not isSize else tmpSize

            columKeys = ['优衣库账号', '日期', '货号', '色号'] + allSize
            endText = f'查询价格：' + text[1] if len(text) == 2 else f'查询价格：'
            columKeys.append(endText)
            data = {i: list() for i in columKeys}

            for currentColor, current in currentInfo.items():
                data['优衣库账号'].append(phone)
                data['日期'].append(date)
                data['货号'].append(goodsNo)
                data['色号'].append(currentColor)

                valid_size = list(current.keys())
                for size in allSize:
                    if size not in valid_size:
                        data[size].append(0)
                    else:
                        data[size].append(current[size])
                data[endText].append(None)
            cls.xlsxAppend(data, filename)

class WangDianTong(object):
    """旺店通"""
    sid = 'drrp02'
    appkey = 'drrp02-ot'
    appsecret = '83819b55d08037ffcace863a0d5fcd71'

    @classmethod
    def getParams(cls, data):
        """根据请求参数获取算法sign，返回整个公共params，后续在请求时公共params使用params传递，请求参数使用data传递"""
        info = {
            "sid": cls.sid,
            "appkey": cls.appkey,
            "timestamp": int(time.time()),
        }
        tmpParams = copy.deepcopy(info)
        for k, v in data.items():
            tmpParams[k] = v
        tmpParams = dict(sorted(tmpParams.items()))
        string = str()
        for k, v in tmpParams.items():
            k_len = '0' + str(len(k.encode('utf8')))
            k_ = k_len[-2:]
            v_len = '000' + str(len(str(v).encode('utf8')))
            v_ = v_len[-4:]
            string += f'{k_}-{k}:{v_}-{v};'
        result = string[:-1] + cls.appsecret

        md5Obj = hashlib.md5()
        md5Obj.update(result.encode('utf8'))
        sign = md5Obj.hexdigest()
        info["sign"] = sign
        return info
    
    @classmethod
    def getShopCode(cls, productCode, size, color):
        """根据千牛的商品编号获取商家编码"""
        url = 'https://api.wangdian.cn/openapi2/goods_query.php'

        now = time.time()
        endTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 0 * 24 * 60 * 60))
        startTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 30 * 24 * 60 * 60))
        data = {
            'startTime': startTime,
            'endTime': endTime,
            'page_no': 0,
            'page_size': 100,
            "warehouse_no": 3,
            "goods_no": productCode,  # 千牛订单的productCode即为goods_no
        }
        params = getParams(data)
        response = requests.post(url, params=params, data=data).json()['goods_list']
        if len(response) == 0:
            return None
        for item in response[0]['spec_list']:
            if item['spec_code'] == size and re.findall(r'[\u4e00-\u9fa5]+', item['spec_name'])[0] == color:
                return item['specNo']  # 商家编号
        return None
    
    @classmethod
    def getStock(cls, specNo):
        """根据货品编号获取库存"""
        url = 'https://api.wangdian.cn/openapi2/stock_query_detail.php'
        now = time.time()
        startTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 30 * 24 * 60 * 60))
        endTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
        data = {
            'startTime': startTime,
            'endTime': endTime,
            'page_no': 0,
            'page_size': 100,
            "warehouse_no": 3,
            "specNo": specNo,
        }
        params = getParams(data)
        response = requests.post(url, params=params, data=data).json()
        response = response.get('stocks')
        if response:
            stock = response[0]['stock_num']
            return int(float(stock))
        else:
            return 0
    
    @classmethod
    def onceModifyWangDianTongOrderShipColor(cls):
        """修改旺店通订单旗帜颜色"""
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        content = now + '千牛系统自动识别库存'
        logger.info(content.center(100, '='))
        logger.info('开始千牛系统登录....')
        orderLogin()
        logger.info('开始获取白色旗帜订单....')
        orderCodes = getOrderCodes('白色')
        logger.info(f'所有订单：{orderCodes}')
        if not orderCodes:
            logger.info('暂无订单可处理')
            return True
        for orderCode in orderCodes:
            orderInfo = getOrderDetail(orderCode, isWrite=False)
            logger.info(f'\n{order}订单：{[i["productTitle"] for i in orderInfo]}')
            for subOrder in orderInfo:
                productCodes = subOrder['productCodes']
                size = subOrder['size']
                color = subOrder['color']
                for productCode in productCodes:
                    shopCode = cls.getShopCode(product, size, color)
                    stock = getStock(shopCode) if shopCode else 0
                    subOrder['stock'] = stock
                    if stock:
                        break
                logger.info(f'{subOrder["fullTitle"]} 库存：{subOrder["stock"]}')
            stocks = [i['stock'] for i in order_info]
            stocks = list(set(stocks))
            if stocks == [0]:
                logger.info(f'{orderCode}订单所有商品均无库存，修改为紫色旗帜')
                modifyOrderStatus(orderCode)
                logger.info(f'{order}订单成功修改为紫色旗帜')
            else:
                logger.info(f'{order}订单存在商品有库存，暂不处理')
        return True

    @classmethod
    def modifyWangOrderShipColor(cls):
        for i in range(10000):
            cls.onceModifyWangDianTongOrderShipColor()
            logger.info(f'等待3分钟再次执行\n')
            time.sleep(3 * 60)

if __name__ == '__main__':
    step = input("请选择执行步骤（1.运行机械臂下单、2.查询优衣库订单信息、3.修改旺店通订单旗帜颜色、4.清空当前登录信息）：")
    if step == '1':
        runRobot()
    elif step == '2':
        Uniqlo.queryUniqloOrder()
    elif step == '3':
        WangDianTong.modifyWangOrderShipColor()
    elif step == '4':
        clear()
    else:
        logger.error('请输入正确的步骤')


