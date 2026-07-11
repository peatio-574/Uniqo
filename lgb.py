#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械臂控制器 Python 封装库
提供面向对象的 API 接口
"""

import sys
from pathlib import Path

# 把项目根目录 D:\robot 加入Python路径
sys.path.append(str(Path(__file__).parent.parent))


import ctypes
import json
import os
from typing import List, Dict, Any
from Logger import logger

dll_file = os.path.join(os.path.dirname(__file__), 'lgb.dll')

class ESP32Controller:
    """机械臂设备控制器"""
    
    # 类变量：DLL 实例（所有对象共享）
    _dll = None
    _dll_loaded = False
    
    def __init__(self, dll_path: str = None):
        """初始化控制器
        
        Args:
            dll_path: DLL 文件路径，默认为当前目录下的 lgb.dll
        """
        dll_path = dll_file if not dll_path else dll_path
        logger.info(dll_path)
        # 加载 DLL（只加载一次）
        if not ESP32Controller._dll_loaded:
            self._load_dll(dll_path)
            ESP32Controller._dll_loaded = True
        
        # 创建控制器句柄
        self._handle = ESP32Controller._dll.CreateController()
        if not self._handle:
            raise RuntimeError("创建控制器失败")
    
    def _load_dll(self, dll_path: str):
        """加载 DLL 并配置函数原型"""
        dll_path = os.path.abspath(dll_path)
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL 文件不存在: {dll_path}")
        
        dll = ctypes.CDLL(dll_path)
        
        # ==========================================
        # 控制器管理接口
        # ==========================================
        dll.CreateController.restype = ctypes.c_void_p
        dll.DestroyController.argtypes = [ctypes.c_void_p]
        dll.GetControllerCount.restype = ctypes.c_int
        
        # ==========================================
        # 专用控制命令接口（直接接受数值参数）
        # ==========================================
        dll.Controller_MoveClick.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int]
        dll.Controller_MoveClick.restype = ctypes.c_char_p
        
        dll.Controller_Drag.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        dll.Controller_Drag.restype = ctypes.c_char_p
        
        dll.Controller_Home.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        dll.Controller_Home.restype = ctypes.c_char_p
        
        # ==========================================
        # TTS 语音播报接口
        # ==========================================
        dll.Controller_PlayAudio.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        dll.Controller_PlayAudio.restype = ctypes.c_char_p
        
        # ==========================================
        # 系统管理接口
        # ==========================================
        dll.Controller_GetStatus.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        dll.Controller_GetStatus.restype = ctypes.c_char_p
        
        dll.Controller_Restart.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        dll.Controller_Restart.restype = ctypes.c_char_p
        
        # ==========================================
        # 拍照与裁剪接口
        # ==========================================
        dll.Controller_CapturePhoto.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        dll.Controller_CapturePhoto.restype = ctypes.c_int
        
        # ==========================================
        # OCR 识别接口
        # ==========================================
        dll.Controller_GetOCR.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        dll.Controller_GetOCR.restype = ctypes.c_char_p
        
        # ==========================================
        # 扫描接口（独立函数）
        # ==========================================
        dll.ScanLanPort.argtypes = [ctypes.c_int]
        dll.ScanLanPort.restype = ctypes.c_char_p
        
        ESP32Controller._dll = dll
    
    def __del__(self):
        """析构函数，自动释放控制器资源"""
        if hasattr(self, '_handle') and self._handle:
            ESP32Controller._dll.DestroyController(self._handle)
            self._handle = None
    
    def __enter__(self):
        """支持上下文管理器（with 语句）如果会用的话，推荐使用"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动释放资源"""
        self.__del__()
    
    # ==========================================
    # 设备控制方法
    # ==========================================
    
    def move_click(self, device_ip: str, x_ratio: float, y_ratio: float, 
                   click_count: int = 1, delay_ms: int = 0, home: bool = False) -> Dict[str, Any]:
        """移动并点击
        
        Args:
            device_ip: 设备 IP 地址
            x_ratio: X百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
            y_ratio: Y百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
            click_count: 点击次数，默认 1
            delay_ms: 按压延迟（毫秒），默认 0  如果长按3秒就写 3000
        
        Returns:
            dict: 响应结果
        
        Examples:
            >>> controller.move_click("192.168.3.200", 0.50000, 0.50000, 1, 0)
            {'success': True, 'message': 'Command executed', 'cmd': 'move_click, 0.50000, 0.50000, 1, 0'}
        """
        result = ESP32Controller._dll.Controller_MoveClick(
            self._handle,
            device_ip.encode('utf-8'),
            x_ratio,
            y_ratio,
            click_count,
            delay_ms
        )
        if home:
            self.home(device_ip)
        return json.loads(result.decode('utf-8'))
    
    def drag(self, device_ip: str, start_x: float, start_y: float,
             end_x: float, end_y: float) -> Dict[str, Any]:
        """拖动操作
        
        Args:
            device_ip: 设备 IP 地址
            start_x: 起点X百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
            start_y: 起点Y百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
            end_x: 终点X百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
            end_y: 终点Y百分比坐标比例 (0.00000 - 1.00000) 推荐精确到小数点后五位
        
        Returns:
            dict: 响应结果
        
        Examples:
            >>> controller.drag("192.168.3.200", 0.10000, 0.10000, 0.90000, 0.90000)
            {'success': True, 'message': 'Command executed', 'cmd': 'drag, 0.10000, 0.10000, 0.90000, 0.90000'}
        """
        result = ESP32Controller._dll.Controller_Drag(
            self._handle,
            device_ip.encode('utf-8'),
            start_x,
            start_y,
            end_x,
            end_y
        )
        return json.loads(result.decode('utf-8'))
        
    def home(self, device_ip: str) -> Dict[str, Any]:
        """归位到原点（复位）
        
        Args:
            device_ip: 设备 IP 地址
        
        Returns:
            dict: 响应结果
        
        Examples:
            >>> controller.home("192.168.3.200")
            {'success': True, 'message': 'Command executed', 'cmd': 'home'}
        """
        result = ESP32Controller._dll.Controller_Home(
            self._handle,
            device_ip.encode('utf-8')
        )
        return json.loads(result.decode('utf-8'))
    
    # ==========================================
    # TTS 语音播报方法
    # ==========================================
    
    def play_audio(self, device_ip: str, text: str) -> Dict[str, Any]:
        """TTS 语音播报
        
        Args:
            device_ip: 设备 IP 地址
            text: 要播报的文本内容（最多 100 个字符, 一个中文是2个字符, 半角标点符号是1个字符）
        
        Returns:
            dict: 响应结果，包含 success、message 字段
        
        Examples:
            >>> controller.play_audio("192.168.3.200", "测试播报")
            {'success': True, 'message': 'Audio playing', 'url': 'http://...'}
        """
        result = ESP32Controller._dll.Controller_PlayAudio(
            self._handle,
            device_ip.encode('utf-8'),
            text.encode('utf-8')
        )
        return json.loads(result.decode('utf-8'))
    
    # ==========================================
    # 系统管理方法
    # ==========================================
    
    def get_status(self, device_ip: str) -> Dict[str, Any]:
        """获取设备状态信息
        
        Args:
            device_ip: 设备 IP 地址
        
        Returns:
            dict: 完整的状态信息，包含 device_id、system_state、wifi_rssi、heap_free、psram_free、uptime、ip 等字段
        
        Examples:
            >>> # 获取完整状态
            >>> status = controller.get_status("192.168.3.200")
            >>> logger.info(status)
            {'data': {'device_id': 'ESP32_001', 'system_state': 'IDLE', 'wifi_rssi': -45, ...}}
            
            >>> # 获取特定字段
            >>> logger.info(status['data']['system_state'])  # IDLE
            >>> logger.info(status['data']['wifi_rssi'])     # -45
        """
        result = ESP32Controller._dll.Controller_GetStatus(
            self._handle,
            device_ip.encode('utf-8')
        )
        return json.loads(result.decode('utf-8'))
    
    def get_ocr(self, server: str, device_ip: str, rotation: int = 0) -> List[Dict[str, Any]]:
        """OCR 识别（调用服务器）
        
        Args:
            server: 服务器地址（如 "127.0.0.1" 或 "http://127.0.0.1:8000"）
            device_ip: 设备 IP 地址
            rotation: 旋转模式（0=0°, 1=90°, 2=180°, 3=270°）
        
        Returns:
            list: 识别结果列表，每项包含 index, text, confidence, box, center 字段
        
        Examples:
            >>> blocks = controller.get_ocr("127.0.0.1", "192.168.3.200", 3)
            >>> for b in blocks:
            ...     logger.info(f"{b['text']} ({b['confidence']:.3f})")
            示例文本 (0.988)
            00:17:51 (0.962)
        """
        result = ESP32Controller._dll.Controller_GetOCR(
            self._handle,
            server.encode('utf-8'),
            device_ip.encode('utf-8'),
            rotation
        )
        
        response = json.loads(result.decode('utf-8'))
        
        # 处理错误
        if response.get('status') == 'error':
            return {'status': 'error', 'error': response.get('error', 'Unknown error')}
        
        # 返回 text_blocks 数组
        data = response.get('data', {})
        return data.get('text_blocks', [])
    
    def restart(self, device_ip: str) -> str:
        """重启系统
        
        Args:
            device_ip: 设备 IP 地址
        
        Returns:
            str: 响应消息
        """
        result = ESP32Controller._dll.Controller_Restart(
            self._handle,
            device_ip.encode('utf-8')
        )
        return result.decode('utf-8')
    
    # ==========================================
    # 拍照与裁剪方法
    # ==========================================
    
    def capture_photo(self, device_ip: str, rotation_mode: int = 1) -> bool:
        """拍照并裁剪图片
        
        Args:
            device_ip: 设备 IP 地址
            rotation_mode: 旋转角度（0=0°, 1=90°, 2=180°, 3=270°）
        
        Returns:
            bool: 是否成功
        
        Examples:
            >>> # 不旋转
            >>> controller.capture_photo("192.168.3.200", 0)
            >>> # 90度旋转
            >>> controller.capture_photo("192.168.3.200", 1)
            >>> # 180度旋转
            >>> controller.capture_photo("192.168.3.200", 2)
            >>> # 270度旋转
            >>> controller.capture_photo("192.168.3.200", 3)
        """
        ret = ESP32Controller._dll.Controller_CapturePhoto(
            self._handle,
            device_ip.encode('utf-8'),
            rotation_mode
        )
        return ret == 0
    
    # ==========================================
    # 静态方法：扫描局域网设备
    # ==========================================
    
    @staticmethod
    def scan_lan(port: int = 8888) -> List[str]:
        """扫描局域网内指定端口的设备
        
        Args:
            port: 端口号，默认 8888
        
        Returns:
            list: IP 地址列表
        
        Examples:
            >>> devices = ESP32Controller.scan_lan(8888)
            >>> logger.info(devices)
            ['192.168.3.200', '192.168.3.201']
        """
        if not ESP32Controller._dll_loaded:
            # 如果 DLL 未加载，先加载
            temp = ESP32Controller()
            temp.__del__()
        
        result = ESP32Controller._dll.ScanLanPort(port)
        return json.loads(result.decode('utf-8'))
    
    @staticmethod
    def get_controller_count() -> int:
        """获取当前控制器数量（调试用）
        
        Returns:
            int: 控制器数量
        """
        if not ESP32Controller._dll_loaded:
            return 0
        return ESP32Controller._dll.GetControllerCount()

    def ocr_text_and_click(self, server: str, device_ip: str, rotation: int = 0, target: str = 'test', keep: int = 200, home: bool = False):
        """拍照识别文案，并点击"""
        location = self.ocr_get_text_location(server=server, device_ip=device_ip, rotation=rotation, target=target)
        if len(location) == 0:
            return False
        self.move_click(device_ip=device_ip, x_ratio=location[0], y_ratio=location[1], click_count=1, delay_ms=keep)
        if home:
            self.home(device_ip)
        return True

    def ocr_get_text_location(self, server: str, device_ip: str, rotation: int = 0, target: str = 'test', home: bool = False , index: int = 1, flag=False):
        """ocr识别图片，返回指定文本的位置，flag为True，完全匹配"""
        self.capture_photo(device_ip, rotation)
        ocr_result = self.get_ocr(server=server, device_ip=device_ip, rotation=rotation)
        ocr_result = ocr_result[::-1] if index == -1 else ocr_result
        location = []
        if ocr_result:
            for i in ocr_result:
                logger.info(i)
                result = target == i['text'] if flag else target in i['text']
                if result:
                    location = i['center']
                    logger.info(f'{i["text"]}文本坐标：{location}')
                    break
        if home:
            self.home(device_ip)
        return location

    def copy(self, device_ip: str, filename: str = None):
        """复制图片并保存"""
        import shutil
        from datetime import datetime
        now = datetime.now()
        pictureDir = os.path.join(os.path.dirname(__file__), 'photo')
        os.makedirs(pictureDir, exist_ok=True)
        tmp_file = os.path.join(pictureDir, f'{device_ip}.jpg')
        fileaname = os.path.join(pictureDir, f'{now.strftime("%Y%m%d-%H%M%S")}.jpg') if not filename else filename
        shutil.copy2(tmp_file, fileaname)
        return True