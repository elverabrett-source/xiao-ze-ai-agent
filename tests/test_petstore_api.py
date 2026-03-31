import pytest
import requests
import json

# 全局变量配置
BASE_URL = "http://example.com/api"  # 假设这是API的基础URL
DEFAULT_HEADERS = {}

# 测试宠物接口
def test_get_pet_by_id():
    """
    测试通过ID获取宠物信息
    """
    # 正常参数测试用例
    response = requests.get(f"{BASE_URL}/pets/1", headers=DEFAULT_HEADERS)
    assert response.status_code == 200, "预期状态码为200，实际为{}".format(response.status_code)
    assert 'id' in response.json(), "响应体中缺少id字段"
    assert 'name' in response.json(), "响应体中缺少name字段"
    assert 'type' in response.json(), "响应体中缺少type字段"

    # 缺失必填项测试用例
    response = requests.get(f"{BASE_URL}/pets/", headers=DEFAULT_HEADERS)
    assert response.status_code == 400, "预期状态码为400，实际为{}".format(response.status_code)

# 测试创建宠物接口
def test_create_pet():
    """
    测试创建宠物
    """
    # 正常参数测试用例
    pet_data = {
        "name": "Fluffy",
        "type": "dog"
    }
    response = requests.post(f"{BASE_URL}/pets/", headers=DEFAULT_HEADERS, json=pet_data)
    assert response.status_code == 201, "预期状态码为201，实际为{}".format(response.status_code)
    assert 'id' in response.json(), "响应体中缺少id字段"
    assert 'name' in response.json(), "响应体中缺少name字段"
    assert 'type' in response.json(), "响应体中缺少type字段"

    # 格式错误测试用例
    pet_data = {
        "name": "Fluffy",
        "type": "invalid_type"
    }
    response = requests.post(f"{BASE_URL}/pets/", headers=DEFAULT_HEADERS, json=pet_data)
    assert response.status_code == 400, "预期状态码为400，实际为{}".format(response.status_code)

# 测试更新宠物接口
def test_update_pet_by_id():
    """
    测试通过ID更新宠物信息
    """
    # 正常参数测试用例
    pet_data = {
        "name": "Fluffy",
        "type": "dog"
    }
    response = requests.put(f"{BASE_URL}/pets/1", headers=DEFAULT_HEADERS, json=pet_data)
    assert response.status_code == 200, "预期状态码为200，实际为{}".format(response.status_code)
    assert 'id' in response.json(), "响应体中缺少id字段"
    assert 'name' in response.json(), "响应体中缺少name字段"
    assert 'type' in response.json(), "响应体中缺少type字段"

    # 缺失必填项测试用例
    pet_data = {
        "name": "Fluffy"
    }
    response = requests.put(f"{BASE_URL}/pets/1", headers=DEFAULT_HEADERS, json=pet_data)
    assert response.status_code == 400, "预期状态码为400，实际为{}".format(response.status_code)

# 测试删除宠物接口
def test_delete_pet_by_id():
    """
    测试通过ID删除宠物
    """
    # 正常参数测试用例
    response = requests.delete(f"{BASE_URL}/pets/1", headers=DEFAULT_HEADERS)
    assert response.status_code == 204, "预期状态码为204，实际为{}".format(response.status_code)

    # 尝试删除不存在的宠物
    response = requests.delete(f"{BASE_URL}/pets/999", headers=DEFAULT_HEADERS)
    assert response.status_code == 404, "预期状态码为404，实际为{}".format(response.status_code)