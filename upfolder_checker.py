#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测父文件夹下的所有git项目，并统计每个项目的untracked files
"""

import os
import subprocess
from pathlib import Path
from urllib.parse import quote


def make_clickable_path(path):
    """将Windows路径转换为可点击的超链接格式（OSC 8标准）"""
    # 将反斜杠转换为正斜杠
    normalized_path = path.replace('\\', '/')
    # 对路径进行URL编码
    encoded_path = quote(normalized_path, safe='/:')
    # 创建file:// URL
    file_url = f"file:///{encoded_path}"
    # 使用OSC 8格式创建超链接
    # 格式: \033]8;;URL\033\\显示文本\033]8;;\033\\
    hyperlink = f"\033]8;;{file_url}\033\\{path}\033]8;;\033\\"
    return hyperlink


def is_git_repo(folder_path):
    """检查文件夹是否是git仓库"""
    git_dir = os.path.join(folder_path, '.git')
    return os.path.isdir(git_dir)


def get_git_status(repo_path):
    """获取git仓库的状态信息"""
    try:
        # 运行 git status 命令
        result = subprocess.run(
            ['git', 'status'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        if result.returncode != 0:
            return None

        output = result.stdout
        status_info = {
            'modified': [],      # 已修改但未暂存
            'staged': [],        # 已暂存
            'untracked': []      # 未跟踪
        }

        # 解析输出
        lines = output.split('\n')
        current_section = None

        for line in lines:
            # 检测不同的section
            if 'Changes to be committed:' in line:
                current_section = 'staged'
                continue
            elif 'Changes not staged for commit:' in line:
                current_section = 'modified'
                continue
            elif 'Untracked files:' in line:
                current_section = 'untracked'
                continue

            # 检测section结束
            if current_section:
                # 空行或非缩进行（不是提示信息）结束当前section
                if line.strip() == '':
                    # 遇到空行，可能结束section，但继续检查
                    pass
                elif not line.startswith('\t') and not line.startswith('  '):
                    # 检查是否是提示信息
                    if ('use "git' in line.lower() or
                        'include in what will be committed' in line.lower() or
                        'no changes added' in line.lower()):
                        continue
                    else:
                        # 非缩进的非提示行，结束section
                        current_section = None
                        continue

                # 提取文件名
                stripped = line.strip()
                if stripped and not stripped.startswith('('):
                    # 对于 modified 和 staged，需要去掉状态前缀（如 "modified:"）
                    if current_section in ['modified', 'staged']:
                        # 处理类似 "modified:   file.txt" 的格式
                        if ':' in stripped:
                            parts = stripped.split(':', 1)
                            if len(parts) == 2:
                                file_name = parts[1].strip()
                                status_prefix = parts[0].strip()
                                status_info[current_section].append(f"{status_prefix}: {file_name}")
                        else:
                            status_info[current_section].append(stripped)
                    elif current_section == 'untracked':
                        status_info[current_section].append(stripped)

        # 只返回有内容的状态信息
        if status_info['modified'] or status_info['staged'] or status_info['untracked']:
            return status_info
        else:
            return None

    except Exception as e:
        print(f"错误: 无法检查 {repo_path}: {e}")
        return None


def scan_directory_for_git_repos(directory):
    """递归扫描指定目录下的所有子目录，查找git仓库"""
    git_repos = []

    try:
        # 使用 os.walk 递归遍历所有子目录
        for root, dirs, files in os.walk(directory):
            # 检查当前目录是否是git仓库
            if is_git_repo(root):
                git_repos.append(root)
                # 如果当前目录是git仓库，不再深入其子目录
                # 因为git仓库内部的.git不算独立仓库
                dirs.clear()
                continue

            # 过滤掉一些不需要扫描的目录（可选优化）
            # 移除以.开头的隐藏目录（除了.git已经在上面处理）
            dirs[:] = [d for d in dirs if not d.startswith('.')]

    except PermissionError:
        # 跳过没有权限访问的目录
        pass
    except Exception as e:
        # 跳过其他错误
        pass

    return git_repos


def main():
    # 获取脚本所在目录的父目录
    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent

    print(f"正在递归扫描上层目录及其所有子目录: {make_clickable_path(str(parent_dir))}")
    print("=" * 80)
    print()

    git_repos = []
    repos_with_changes = []
    total_modified_count = 0
    total_staged_count = 0
    total_untracked_count = 0

    # 扫描父目录下的所有git仓库（递归）
    print(f"正在扫描...")
    repos_in_dir = scan_directory_for_git_repos(parent_dir)

    # 检查每个git仓库的状态
    for repo_path in repos_in_dir:
        repo_name = os.path.basename(repo_path)
        git_repos.append(repo_path)

        # 获取git状态
        status_info = get_git_status(repo_path)

        if status_info:
            repos_with_changes.append({
                'name': repo_name,
                'path': repo_path,
                'status': status_info
            })
            total_modified_count += len(status_info['modified'])
            total_staged_count += len(status_info['staged'])
            total_untracked_count += len(status_info['untracked'])

    print()
    print("=" * 80)

    # 输出结果
    print(f"找到 {len(git_repos)} 个 Git 仓库")
    print(f"其中 {len(repos_with_changes)} 个仓库有变更")
    print()

    if repos_with_changes:
        print("=" * 80)
        print("有变更的仓库详情:")
        print("=" * 80)
        print()

        for repo in repos_with_changes:
            print(f"📁 {repo['name']}")
            print(f"   路径: {make_clickable_path(repo['path'])}")

            status = repo['status']

            # 显示已暂存的文件
            if status['staged']:
                print(f"   ✓ 已暂存 (Changes to be committed): {len(status['staged'])} 个文件")
                for file in status['staged']:
                    print(f"      - {file}")

            # 显示已修改但未暂存的文件
            if status['modified']:
                print(f"   ⚠ 已修改未暂存 (Changes not staged for commit): {len(status['modified'])} 个文件")
                for file in status['modified']:
                    print(f"      - {file}")

            # 显示未跟踪的文件
            if status['untracked']:
                print(f"   ? 未跟踪 (Untracked files): {len(status['untracked'])} 个文件")
                for file in status['untracked']:
                    print(f"      - {file}")

            print()

        print("=" * 80)
        print(f"总计:")
        print(f"  已暂存: {total_staged_count} 个文件")
        print(f"  已修改未暂存: {total_modified_count} 个文件")
        print(f"  未跟踪: {total_untracked_count} 个文件")
        print("=" * 80)
    else:
        print("✓ 所有Git仓库都是干净的状态（没有变更）")


if __name__ == '__main__':
    main()
    input("Press Enter to continue...")
