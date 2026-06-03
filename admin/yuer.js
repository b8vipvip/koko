 // ✅ 设备列表：以后新增设备只需要加一行
const BALANCE_DEVICE_IDS = [157, 178, 188,198];
// 获取设备实时余额（只显示整数）
function fetchBalances() {
  fetch('/phpapi/get_balances.php')
    .then(res => res.json())
    .then(data => {
      BALANCE_DEVICE_IDS.forEach(id => {
        const key = `balance_${id}`;
        // 接口可能没有返回某个设备（比如你现在 get_balances.php 可能只返回157/178）
        if (!(key in data)) return;

        const el = document.getElementById(key);
        // ✅ 元素不存在（还没 renderDevices()）就直接跳过，不报错
        if (!el) return;

        // ✅ 只保留整数（不要小数）
        const n = Number(data[key]);
        el.textContent = Number.isFinite(n) ? Math.floor(n) : 0;
      });
    })
    .catch(err => console.error('获取余额时出错:', err));
}

// ✅ 不要用 window.onload 覆盖别人的 onload（你页面里可能还有其他 onload）
// 改用 DOMContentLoaded，并延迟一点点，确保 renderDevices 已经生成 balance_xxx
document.addEventListener('DOMContentLoaded', () => {
  // 如果你的 renderDevices() 在另一个脚本里，且不确定加载顺序，用 setTimeout 更稳
  setTimeout(() => {
    fetchBalances();
    // 可选：每5秒刷新一次余额
    setInterval(fetchBalances, 5000);
  }, 0);
});
    // 向设备转入资金或转出资金
    function transferFunds(isTransferIn) {
        let amount = isTransferIn
            ? document.getElementById('fund_in').value
            : document.getElementById('manual_fund_out').value;

        let deviceId = isTransferIn
            ? document.getElementById('device_in').value
            : document.getElementById('device_out').value;

        if (isNaN(amount) || amount <= 0) {
            alert('请输入有效的金额');
            return;
        }

        let apiUrl = isTransferIn ? '/phpapi/transfer_in.php' : '/phpapi/transfer_out.php'; // ✅ 后端接口路径
        fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: parseInt(deviceId), amount: parseFloat(amount) })
        })
        .then(response => response.json())
        .then(data => {
            alert('操作成功！设备 ' + deviceId + ' 当前余额: ' + data.balance);
            fetchBalances();  // ✅ 成功后刷新余额
        })
        .catch(error => {
            console.error('资金转移出错:', error);
        });
    }

    // 查询资金明细
    function queryFunds() {
        let startDate = document.getElementById('start_date').value;
        let endDate = document.getElementById('end_date').value;

        if (!startDate || !endDate) {
            alert('请选择有效的日期范围');
            return;
        }

        fetch('/phpapi/fund_summary.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_date: startDate + " 00:00:00",
                end_date: endDate + " 23:59:59"
            })
        })
        .then(response => response.json())
        .then(data => {
            let resultText = `
                转入资金总和: ${data.total_fund_in || 0}<br>
                手动转出资金总和: ${data.total_manual_fund_out || 0}<br>
                自动转出资金总和: ${data.total_auto_fund_out || 0}<br>
                总转出资金: ${data.total_fund_out || 0}<br>
            `;
            document.getElementById('result').innerHTML = resultText;
        })
        .catch(error => {
            console.error('查询资金明细时出错:', error);
        });
    }

    // 页面加载时获取设备余额
   // window.onload = fetchBalances;
 
function toggleDateInput() {
    const range = document.getElementById('profit-range').value;
    const dateInput = document.getElementById('specific-date');
    dateInput.style.display = (range === 'specific') ? 'inline-block' : 'none';
}

function queryProfit() {
    const range = document.getElementById('profit-range').value;
    const date = document.getElementById('specific-date').value;

    fetch('/profit_stat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ range: range, date: date })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`💰 统计结果：${data.range_label} 的利润总和为：${data.total_profit}`);
        } else {
            alert('❌ 查询失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('❌ 网络错误，请稍后再试');
    });
}