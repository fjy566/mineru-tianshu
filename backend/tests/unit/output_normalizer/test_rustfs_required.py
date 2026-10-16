"""含图片的任务必须使用 RustFS 或本机 API 文件服务；都未启用时必须失败。

历史问题：RUSTFS_ENABLED=false 时图片保留相对路径，前端无法访问；
本机开发模式现在使用鉴权 API 文件接口提供这些图片。
"""

import pytest

from output_normalizer.base_output_normalizer import BaseOutputNormalizer


@pytest.fixture
def normalizer():
    return BaseOutputNormalizer.__new__(BaseOutputNormalizer)


@pytest.fixture
def result_with_images(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    (img_dir / "a.jpg").write_bytes(b"x")
    return {
        "image_dir": img_dir,
        "image_count": 1,
        "markdown_file": tmp_path / "result.md",
        "json_file": None,
    }


class TestRustfsRequired:
    def test_disabled_raises(self, normalizer, result_with_images, monkeypatch):
        monkeypatch.setenv("RUSTFS_ENABLED", "false")
        monkeypatch.setenv("TIANSHU_LOCAL_FILE_SERVER_ENABLED", "false")

        with pytest.raises(RuntimeError, match="本地 API 图片服务"):
            normalizer._process_rustfs_upload(result_with_images)

    def test_local_file_server_keeps_images_local(self, normalizer, result_with_images, monkeypatch, mocker):
        monkeypatch.setenv("RUSTFS_ENABLED", "false")
        monkeypatch.setenv("TIANSHU_LOCAL_FILE_SERVER_ENABLED", "true")
        upload = mocker.patch.object(BaseOutputNormalizer, "_upload_images_to_rustfs")

        normalizer._process_rustfs_upload(result_with_images)

        upload.assert_not_called()
        assert result_with_images["rustfs_enabled"] is False
        assert result_with_images["images_uploaded"] is False
        assert result_with_images["images_local"] is True

    def test_upload_exception_raises_with_actionable_message(self, normalizer, result_with_images, monkeypatch, mocker):
        monkeypatch.setenv("RUSTFS_ENABLED", "true")
        mocker.patch.object(
            BaseOutputNormalizer, "_upload_images_to_rustfs", side_effect=ConnectionError("connection refused")
        )

        with pytest.raises(RuntimeError, match="RUSTFS_ENDPOINT"):
            normalizer._process_rustfs_upload(result_with_images)

    def test_empty_mapping_raises(self, normalizer, result_with_images, monkeypatch, mocker):
        """上传"成功"但一个地址都没返回，同样不能当成功"""
        monkeypatch.setenv("RUSTFS_ENABLED", "true")
        mocker.patch.object(BaseOutputNormalizer, "_upload_images_to_rustfs", return_value={})

        with pytest.raises(RuntimeError, match="未返回任何地址"):
            normalizer._process_rustfs_upload(result_with_images)

    def test_success_marks_uploaded(self, normalizer, result_with_images, monkeypatch, mocker):
        monkeypatch.setenv("RUSTFS_ENABLED", "true")
        mocker.patch.object(
            BaseOutputNormalizer, "_upload_images_to_rustfs", return_value={"a.jpg": "http://host/s3/b/a.jpg"}
        )
        replace = mocker.patch.object(BaseOutputNormalizer, "_replace_markdown_urls")

        normalizer._process_rustfs_upload(result_with_images)

        assert result_with_images["rustfs_enabled"] is True
        assert result_with_images["images_uploaded"] is True
        replace.assert_called_once()

    def test_documents_without_images_never_touch_rustfs(self, tmp_path, mocker):
        """无图文档不应受对象存储可用性影响"""
        upload = mocker.patch.object(BaseOutputNormalizer, "_process_rustfs_upload")
        n = BaseOutputNormalizer.__new__(BaseOutputNormalizer)
        mocker.patch.object(
            BaseOutputNormalizer,
            "_normalize_local_files",
            return_value={"markdown_file": None, "json_file": None, "image_dir": None, "image_count": 0},
        )

        n.normalize(tmp_path)

        upload.assert_not_called()
