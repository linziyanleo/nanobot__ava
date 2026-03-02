#!/usr/bin/env python3
"""
restart_with_restore.py - Gateway 重启并自动恢复状态

功能：
1. 保存当前 gateway 状态到文件
2. 创建一次性 cron 任务（重启后 30 秒执行恢复）
3. 优雅关闭当前 gateway
4. 重新启动 gateway
5. 恢复任务自动执行并汇报

使用方法：
    python3 restart_with_restore.py [--delay <seconds>] [--force]

参数：
    --delay <seconds>  延迟重启时间（默认：5 秒）
    --force           强制重启（跳过优雅关闭）
    --help            显示帮助信息
"""

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def log_info(message: str) -> None:
    """打印信息日志"""
    print(f"\033[0;32m[INFO]\033[0m {message}")


def log_warn(message: str) -> None:
    """打印警告日志"""
    print(f"\033[1;33m[WARN]\033[0m {message}")


def log_error(message: str) -> None:
    """打印错误日志"""
    print(f"\033[0;31m[ERROR]\033[0m {message}")


def find_gateway_pid() -> int | None:
    """查找 gateway 进程 PID"""
    try:
        # 方法 1: pgrep 查找
        result = subprocess.run(
            ["pgrep", "-f", "nanobot gateway"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        
        # 方法 2: ps + grep
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if 'nanobot gateway' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
    except Exception as e:
        log_error(f"查找 PID 失败：{e}")
    
    return None


def save_state(state_file: Path) -> dict:
    """保存当前状态到文件"""
    state = {
        "restart_time": datetime.datetime.now().isoformat(),
        "restart_reason": "用户请求重启",
        "hostname": os.uname().nodename,
        "python_version": sys.version,
        "tasks_to_check": [
            "sync-upstream",
            "daily_cold_joke", 
            "weight_reset",
            "weight_check",
            "早晨日常提醒",
            "父亲生日提醒"
        ],
        "checks": [
            "gateway 进程是否正常",
            "cron 任务是否正常",
            "配置文件是否加载",
            "会话是否保留"
        ],
        "report_to": {
            "channel": "telegram",
            "chat_id": "-5172087440"
        }
    }
    
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    log_info(f"状态已保存到：{state_file}")
    return state


def create_restore_task(state_file: Path, delay_seconds: int = 30) -> str:
    """创建一次性恢复任务"""
    try:
        from nanobot.cron.service import CronService
        from nanobot.cron.types import CronSchedule
        
        # 计算执行时间（重启后 delay_seconds 秒）
        execute_time = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
        at_ms = int(execute_time.timestamp() * 1000)
        
        # 读取状态文件内容
        state = json.loads(state_file.read_text())
        
        # 创建 cron 服务
        store_path = Path.home() / ".nanobot" / "cron" / "jobs.json"
        service = CronService(store_path=store_path)
        
        # 创建恢复任务
        schedule = CronSchedule(kind="at", at_ms=at_ms)
        job = service.add_job(
            name="gateway_restore",
            schedule=schedule,
            message=f"""🔄 Gateway 重启恢复任务

📋 任务清单：
1. 读取状态文件：{state_file}
2. 检查 gateway 进程是否正常启动
3. 检查 cron 任务列表是否正常
4. 验证以下任务是否存在：
   {chr(10).join('   - ' + task for task in state['tasks_to_check'])}
5. 向 Leo 汇报恢复结果

📊 重启信息：
- 重启时间：{state['restart_time']}
- 重启原因：{state['restart_reason']}
- 主机名：{state['hostname']}

✅ 完成后请删除状态文件并汇报：
"Gateway 重启完成！所有系统正常 ✨"
""",
            deliver=True,
            channel=state["report_to"]["channel"],
            to=state["report_to"]["chat_id"],
            delete_after_run=True,  # 执行后自动删除
        )
        
        log_info(f"恢复任务已创建：{job.id}")
        log_info(f"执行时间：{execute_time.strftime('%Y-%m-%d %H:%M:%S')}（{delay_seconds}秒后）")
        
        return job.id
        
    except Exception as e:
        log_error(f"创建恢复任务失败：{e}")
        log_warn("将继续重启，但不会自动恢复")
        return None


def stop_gateway(pid: int, force: bool = False) -> bool:
    """停止 gateway 进程"""
    try:
        if force:
            log_warn("强制模式：发送 SIGKILL")
            os.kill(pid, signal.SIGKILL)
        else:
            log_info("发送 SIGTERM 进行优雅关闭...")
            os.kill(pid, signal.SIGTERM)
            
            # 等待进程退出（最多 10 秒）
            for i in range(10):
                time.sleep(1)
                if find_gateway_pid() is None:
                    log_info("Gateway 已优雅关闭")
                    return True
            
            log_warn("优雅关闭超时，发送 SIGKILL")
            os.kill(pid, signal.SIGKILL)
        
        time.sleep(1)
        
        # 验证进程是否已停止
        if find_gateway_pid() is None:
            log_info("Gateway 已停止")
            return True
        else:
            log_error("Gateway 仍未停止")
            return False
            
    except ProcessLookupError:
        log_info("进程已不存在")
        return True
    except Exception as e:
        log_error(f"停止失败：{e}")
        return False


def start_gateway() -> int | None:
    """启动新的 gateway 实例"""
    try:
        log_info("启动新的 gateway 实例...")
        
        # 使用 nohup 后台运行
        subprocess.Popen(
            ["nanobot", "gateway"],
            stdout=open("/tmp/nanobot_gateway.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # 等待启动
        time.sleep(3)
        
        # 验证启动
        new_pid = find_gateway_pid()
        if new_pid:
            log_info(f"Gateway 启动成功！PID: {new_pid}")
            return new_pid
        else:
            log_error("Gateway 启动失败，请检查日志：/tmp/nanobot_gateway.log")
            return None
            
    except Exception as e:
        log_error(f"启动失败：{e}")
        return None


def restart_gateway(delay_seconds: int = 5, force: bool = False) -> bool:
    """执行重启流程"""
    log_info("=" * 50)
    log_info("🔄 Nanobot Gateway 重启流程")
    log_info("=" * 50)
    
    # 1. 查找当前 gateway
    current_pid = find_gateway_pid()
    if not current_pid:
        log_warn("未找到运行中的 gateway")
        log_info("将直接启动新的 gateway")
        return start_gateway() is not None
    
    log_info(f"当前 gateway PID: {current_pid}")
    
    # 2. 保存状态
    state_file = Path("/tmp/gateway_restart_state.json")
    state = save_state(state_file)
    
    # 3. 创建恢复任务（重启后 30 秒执行）
    restore_delay = 30  # 重启后 30 秒执行恢复
    job_id = create_restore_task(state_file, restore_delay)
    
    if not job_id:
        log_warn("恢复任务创建失败，是否继续重启？(y/n)")
        try:
            response = input().strip().lower()
            if response != 'y':
                log_info("已取消重启")
                return False
        except:
            pass
    
    # 4. 延迟等待
    log_info(f"{delay_seconds}秒后开始重启...")
    log_warn("按 Ctrl+C 可取消")
    
    try:
        for i in range(delay_seconds, 0, -1):
            print(f"\r  剩余时间：{i}秒 ", end='', flush=True)
            time.sleep(1)
        print()  # 换行
    except KeyboardInterrupt:
        log_info("\n已取消重启")
        return False
    
    # 5. 停止当前 gateway
    log_info("正在停止当前 gateway...")
    if not stop_gateway(current_pid, force):
        log_error("停止失败，尝试强制停止")
        if not stop_gateway(current_pid, force=True):
            log_error("无法停止 gateway，重启失败")
            return False
    
    # 6. 启动新的 gateway
    log_info("正在启动新的 gateway...")
    new_pid = start_gateway()
    
    if not new_pid:
        log_error("启动失败，重启未完成")
        return False
    
    # 7. 总结
    log_info("=" * 50)
    log_info("✅ 重启完成！")
    log_info("=" * 50)
    log_info(f"新 PID: {new_pid}")
    log_info(f"恢复任务：{job_id or '未创建'}")
    log_info(f"恢复时间：{datetime.datetime.now() + datetime.timedelta(seconds=restore_delay)}")
    log_info(f"状态文件：{state_file}")
    log_info("")
    log_info("Gateway 将在后台运行，恢复任务会自动执行并汇报结果 ✨")
    
    # 8. 关闭当前脚本（重要！）
    log_info("\n当前脚本即将退出...")
    time.sleep(2)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Gateway 重启并自动恢复状态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 restart_with_restore.py              # 5 秒后重启
  python3 restart_with_restore.py --delay 10   # 10 秒后重启
  python3 restart_with_restore.py --force      # 强制重启
        """
    )
    
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="延迟重启时间（秒），默认：5"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重启（跳过优雅关闭）"
    )
    
    args = parser.parse_args()
    
    try:
        success = restart_gateway(
            delay_seconds=args.delay,
            force=args.force
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log_info("\n已取消")
        sys.exit(1)
    except Exception as e:
        log_error(f"重启失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
