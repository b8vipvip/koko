const ADMIN_API_BASE = "";

function adminApi(path) {
    return ADMIN_API_BASE + path;
}

let currentPage = 1;
let totalPages = 1;



function updateStatus() {
    fetch('/dev.php')
    .then(response => {
        return response.text(); // 先取原始文本
    })
    .then(text => {
        try {
            const data = JSON.parse(text); // 手动解析 JSON
            console.log("解析成功", data);

            const device1Label = document.getElementById('device1Status').querySelector('label');
            device1Label.textContent = data.device1.status;
            device1Label.style.backgroundColor = data.device1.background;

            const device2Label = document.getElementById('device2Status').querySelector('label');
            device2Label.textContent = data.device2.status;
            device2Label.style.backgroundColor = data.device2.background;
            

        } catch (e) {
            console.error("返回的不是合法 JSON：", text);
        }
    })
    .catch(error => {
        console.error("fetch 请求失败：", error);
    });
}

// 页面加载时调用函数
document.addEventListener('DOMContentLoaded', updateStatus);
// 获取数据并渲染列表
function fetchData(tel = '', page = 1) {
    fetch(adminApi(`/api.php?action=search&tel=${tel}&page=${page}`))
        .then(response => response.json())
        .then(data => {
            displayRecords(data.records);
            currentPage = data.current_page;
            totalPages = data.total_pages;
            updatePagination();
        })
        .catch(error => console.error('Error:', error));
}



function displayRecords(records) {
    if (!Array.isArray(records)) {
        console.error("Expected an array of records, but got:", records);
        return;
    }
    const tableBody = document.getElementById("data-table");
    tableBody.innerHTML = "";
    records.forEach(record => {
        // console.log(record);  // 调试查看 record 的内容
        const row = document.createElement("tr");

        // 设置操作按钮
        let buttonHtml = '';
        if (record.c_status === "1") {  // 判断 c_status 是否是字符串 '1'
            //buttonHtml = `<button onclick="handleSkip(${record.id})" style="background-color: #00cc66;">拦截</button>`;
            buttonHtml = `<button type="button" onclick="handleSkip(${record.id})"style="background-color: #00cc66;">拦截</button>`;
            
        } else if (record.c_status === "2") {
            buttonHtml = `<button disabled style="background-color: grey;">拦截</button>`;
        }

        // 设置 r_status 字段及其颜色
        let rStatusColor = "";
        if (record.r_status === "超时") {
            rStatusColor = "red";
        } else if (record.r_status === "成功") {
            rStatusColor = "green";
        } else if (record.r_status === "已成功") {
            rStatusColor = "green";
        } else if (record.r_status === "充值成功") {
            rStatusColor = "green";    
        } else if (record.r_status === "已发送") {
            rStatusColor = "green";
        }else if (record.r_status === "失败") {
            rStatusColor = "red";
        } else if (record.r_status === "卡了") {
            rStatusColor = "red";
        } else if (record.r_status === "已拦截") {
            rStatusColor = "red";
        } else if (record.r_status === "验证错") {
            rStatusColor = "red";
        } 
        

        row.innerHTML = `
            <td>${record.create_date}</td>
            <td onclick="copyToClipboard('${record.tel}')" style="color: #1E9FFF;">${record.tel}</td>
            <td>${record.zhanghu}</td>
            <td>${record.pxtype}</td>
            <td style="color: ${rStatusColor};"><a href="#" onclick="showDetails(${record.id})" style="text-decoration: underline; color: inherit;">${record.r_status}</a></td>
            <td>${buttonHtml}</td>
        `;
        tableBody.appendChild(row);
    });
}










// 实现复制到剪切板的函数并显示悬浮消息
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast("已复制");
    }).catch(err => {
        console.error('复制失败: ', err);
    });
}

// 显示悬浮消息的函数
function showToast(message) {
    const toast = document.createElement("div");
    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.backgroundColor = "rgba(0, 0, 0, 0.7)";
    toast.style.color = "#fff";
    toast.style.padding = "10px 20px";
    toast.style.borderRadius = "5px";
    toast.style.zIndex = "1000";
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";

    document.body.appendChild(toast);

    // 让悬浮消息逐渐显示
    setTimeout(() => {
        toast.style.opacity = "1";
    }, 100);

    // 2秒后自动消失
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300); // 等待淡出动画完成后移除元素
    }, 2000);
}



// 处理跳过按钮点击的函数
/*
function handleSkip(id) {
    // 发起AJAX请求来检查和更新c_status
    console.log('Sending request to skip ID:', id);
    fetch(adminApi(`/api.php?action=check_and_update_c_status`), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: id })
    })
    .then(response => {
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    return response.json();
})

    //.then(response => response.json())
    .then(data => {
        console.log(data);  // 查看返回的数据结构
        displayRecords(data);
        if (data.success) {
            showToast("拦截成功");
            // 重新加载数据，或更新页面中的按钮状态
            loadRecords();
        } else {
            showToast("拦截失败");
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}
console.log('Sending request to skip ID:');
*/
// 处理跳过按钮点击的函数
// 处理跳过按钮点击的函数（带详细调试日志版）
function handleSkip(id) {
    console.log('🟣 handleSkip 被调用，参数 id =', id);

    if (!id) {
        console.warn("🟠 handleSkip 中 id 无效！");
        showToast("❌ 无效的ID，无法拦截");
        return;
    }

    const requestUrl = adminApi('/api.php?action=check_and_update_c_status');
    console.log('🟣 即将发送 fetch 请求到：', requestUrl);

    const requestBody = JSON.stringify({ id: id });
    console.log('🟣 请求 body：', requestBody);

    fetch(requestUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: requestBody
    })
    .then(response => {
        console.log('🟣 fetch 响应状态码：', response.status);
        console.log('🟣 fetch 响应 ok? ', response.ok);
        console.log('🟣 fetch 响应 headers：', response.headers);

        if (!response.ok) {
            throw new Error('❌ 网络响应失败，状态码：' + response.status);
        }
        return response.text();
    })
    .then(text => {
        console.log('🟣 原始返回文本：', text);
        try {
            const data = JSON.parse(text);
            console.log('🟣 解析后的 JSON：', data);

            if (data.success) {
                showToast("✅ 拦截成功：" + (data.message || ""));
                // 重新加载数据，或更新页面中的按钮状态
                loadRecords();
            } else {
                showToast("❌ 拦截失败：" + (data.message || ""));
            }
        } catch (err) {
            console.error('❌ JSON 解析错误：', err);
            showToast("❌ 服务器返回格式错误，请联系管理员");
        }
    })
    .catch(error => {
        console.error('❌ fetch 发生异常：', error);
        showToast("❌ 网络或服务器错误，请稍后再试");
    });
}


// 加载数据的函数

function loadRecords() {
    console.log('🟣 调用 loadRecords() - 刷新列表');
    fetch(adminApi('/api.php?action=search&page=1'))
        .then(response => response.json())
        .then(data => {
            console.log('🟣 loadRecords 拿到数据：', data);
            displayRecords(data.records);
        })
        .catch(error => {
            console.error('❌ loadRecords 出错:', error);
            showToast("❌ 无法加载最新记录");
        });
}


function showDetails(id) {
    console.log(`Fetching details for ID: ${id}`); // 打印正在获取详情的 ID

    fetch(adminApi(`/api.php?action=getDetails&id=${id}`))
        .then(response => {
            if (!response.ok) {
                console.error(`Network error: ${response.status} ${response.statusText}`); // 打印响应的状态码和状态文本
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Data received:', data); // 打印从后端获取到的数据

            if (data) {
                // 显示 details 内容
                const detailsInfo = data.details || 'No details available';
                console.log('Details:', detailsInfo); // 打印 details 内容
                document.getElementById('details-info').innerHTML = detailsInfo.replace(/\n/g, '<br>');

                // 显示 userid
                if (data.userid) {
                    console.log('UserID:', data.userid);
                    const useridElement = document.createElement('div');
                    useridElement.style.fontSize = '0.85em';
                    useridElement.style.color = '#0176c4';
                    useridElement.style.cursor = 'pointer';
                    useridElement.setAttribute('onclick', `copyToClipboard('${data.userid}')`);
                    useridElement.textContent = `用户ID: ${data.userid}`;
                
                    // 插到 #details-info 下面
                    document.getElementById('details-info').insertAdjacentElement('afterend', useridElement);
                } else {
                    console.warn('UserID not found in the data');
                }
            
                // 检查和设置 <a> 标签的 href 属性
                if (data.url) {
                    console.log('Setting URL for details-img1:', data.url); // 打印 img1 链接
                    document.getElementById('details-img1-link').href = data.url;
                } else {
                    console.warn('URL for details-img1 is missing');
                    document.getElementById('details-img1-link').href = '#';
                }

                if (data.url1) {
                    console.log('Setting URL for details-img2:', data.url1); // 打印 img2 链接
                    document.getElementById('details-img2-link').href = data.url1;
                } else {
                    console.warn('URL for details-img2 is missing');
                    document.getElementById('details-img2-link').href = '#';
                }

                // ✅ 在这里绑定“手动成功”按钮点击事件
                document.getElementById('sd-czcg-btn').onclick = function() {
                    console.log(`Manually marking ID ${id} as 成功`);

                    fetch(adminApi('/api.php?action=setManualSuccess'), {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: `id=${encodeURIComponent(id)}`
                    })
                    .then(res => res.json())
                    .then(result => {
                        if (result.success) {
                            showToast('✅ 已标记为成功');
                        } else {
                            showToast('❌ 操作失败：' + result.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showToast('❌ 网络错误，请稍后再试');
                    });
                };

            } else {
                console.error('No data returned from the server');
            }

            document.getElementById("data-table").style.display = 'none';
            document.getElementById("details-container").style.display = 'block';
        })
        .catch(error => {
            console.error('Error:', error); // 打印捕获到的错误
            alert('An error occurred while fetching details. Please try again later.');
        });
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    layer.msg("已复制");
  }).catch(() => {
    layer.msg("复制失败");
  });
}

// 复制消息的功能（改用 showToast 提示）
document.getElementById('copy-message-btn').addEventListener('click', function () {
    const detailsText = document.getElementById('details-info').innerText;
    const match = detailsText.match(/\[(.*?)\]/); // 查找第一组被“[”和“]”括起来的内容
    if (match && match[1]) {
        const textToCopy = match[1]; // 提取括号内的内容
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('消息已复制到剪贴板');
        }).catch(err => {
            console.error('复制到剪贴板失败:', err);
            showToast('复制失败，请重试');
        });
    } else {
        showToast('未找到需要复制的内容');
    }
});



// 返回列表页
function goBack() {
    fetchData();
    // document.getElementById("data-table").style.display = 'block';
    // document.getElementById("details-container").style.display = 'none';
}

// 更新分页显示
function updatePagination() {
    document.getElementById("pageInfo").innerText = `第 ${currentPage} 页`;
    document.getElementById("prevPage").classList.toggle("disabled", currentPage <= 1);
    document.getElementById("nextPage").classList.toggle("disabled", currentPage >= totalPages);
}

// 跳转到指定页
function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    fetchData('', page);
}

// 上一页/下一页翻页
function changePage(offset) {
    const newPage = currentPage + offset;
    if (newPage < 1 || newPage > totalPages) return;
    fetchData('', newPage);
}

// 更新 URL 参数
function updateURLParameter(key, value) {
    const url = new URL(window.location);
    url.searchParams.set(key, value);
    window.history.pushState({}, '', url); // 修改 URL 而不刷新页面
}

// 页面加载时初始化
document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const tel = urlParams.get("tel");
    if (tel) {
        document.getElementById("search-input").value = tel;
        fetchData(tel); // 自动搜索
    }
});

// 搜索手机号或者卡密
function searchRecords() {
    const keyword = document.getElementById("search-input").value.trim();
    if (!keyword) {
        layer.msg("请输入手机号或兑换码！");
        return;
    }
    updateURLParameter('tel', keyword); // 动态更新 URL
    fetchData(keyword);
}
/*
//更新卡密为已使用
function markOrderIDUsed() {
    const input = document.getElementById("search-input").value.trim();

    if (!input) {
        layer.msg("请输入兑换码！");
        return;
    }

    // 判断是不是手机号
    if (/^\d{11}$/.test(input)) {
        layer.msg("输入的是手机号，无法标记为已使用！");
        return;
    }

    // 是卡密，调用后端接口
    fetch(adminApi('/mark_order_used'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ orderID: input })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('网络错误');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            layer.msg('✅ 兑换码已成功标记为已使用！');
        } else {
            layer.msg('❌ 操作失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        layer.msg('❌ 网络错误，请稍后重试');
    });
}
*/
function clockorderID() {
    const input = document.getElementById("search-input").value.trim();

    if (!input) {
        layer.msg("请输入兑换码！");
        return;
    }

    // 判断是不是手机号
    if (/^\d{11}$/.test(input)) {
        layer.msg("输入的是手机号，无法锁定！");
        return;
    }

    // 调用后端接口，将状态设为2
    fetch(adminApi('/mark_order_used'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ orderID: input, status: 2 })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            layer.msg('✅ 兑换码已成功锁定（status=2）！');
        } else {
            layer.msg('❌ 操作失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        layer.msg('❌ 网络错误，请稍后重试');
    });
}


function unclockorderID() {
    const input = document.getElementById("search-input").value.trim();

    if (!input) {
        layer.msg("请输入兑换码！");
        return;
    }

    // 判断是不是手机号
    if (/^\d{11}$/.test(input)) {
        layer.msg("输入的是手机号，无法解锁！");
        return;
    }

    // 调用后端接口，将状态设为1
    fetch(adminApi('/mark_order_used'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ orderID: input, status: 1 })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            layer.msg('✅ 兑换码已成功解锁（status=1）！');
        } else {
            layer.msg('❌ 操作失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        layer.msg('❌ 网络错误，请稍后重试');
    });
}

function goHome() {
    // 1️⃣ 清空输入框
    document.getElementById("search-input").value = '';

    // 2️⃣ 重置URL参数
    updateURLParameter('tel', '');

    // 3️⃣ 加载第一页
    fetchData('', 1);
}

// 初始化加载第一页
fetchData();
