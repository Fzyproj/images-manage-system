from flask import Flask, request, jsonify
import subprocess
import json

from entity.repo_image import RepoImage

app = Flask(__name__)

# 配置阿里云仓库地址
ALIYUN_REGISTRY = "crpi-lsey5sghxxwk05fh.cn-hangzhou.personal.cr.aliyuncs.com"
APP_NAMESPACE = "app_ns"

# 查询本地镜像列表
@app.route("/images", methods=["GET"])
def list_images():
    try:
        # 获取镜像列表，每一行是一个 JSON
        result = subprocess.check_output(
            'docker images --format "{{json .}}"',
            shell=True,
            encoding="utf-8"
        )
        # 每行一个 JSON，逐行解析
        images = []
        for line in result.strip().split("\n"):
            if line:
                image_info = json.loads(line)
                repo_image = RepoImage(image_info['ID'], image_info['Repository'], image_info['Tag'])
                images.append(repo_image.to_dict())

        return jsonify({"status": "success", "data": images})

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)})


# 打 tag、push、删除临时 tag
@app.route("/push-image", methods=["POST"])
def push_image():
    data = request.get_json()
    local_image = data.get("local_image")
    version = data.get("version")

    if not local_image or not version:
        return jsonify({"status": "error", "message": "缺少 local_image 或 version 参数"}), 400

    aliyun_image = f"{ALIYUN_REGISTRY}/{APP_NAMESPACE}/{local_image}:{version}"

    try:
        # 打 tag
        subprocess.check_call(["docker", "tag", f"{local_image}:{version}", aliyun_image])

        # 推送
        subprocess.check_call(["docker", "push", aliyun_image])

        # 删除 tag 镜像
        subprocess.check_call(["docker", "rmi", aliyun_image])

        return jsonify({"status": "success", "message": f"{aliyun_image} 已推送并清理"}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)
