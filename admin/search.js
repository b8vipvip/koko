const ADMIN_API_BASE = "";

function adminApi(path) {
    return ADMIN_API_BASE + path;
}

// 搜索手机号
function searchRecords() {
    const tel = document.getElementById("search-input").value;

    // 发起请求到后端 API
    fetch(adminApi(`/api.php?action=search&tel=${encodeURIComponent(tel)}`))
        .then(response => response.json())
        .then(data => {
            if (data.records && data.records.length > 0) {
                console.log("查询结果:", data.records);
                // 在页面上显示数据或更新 UI 逻辑
                // displayResults(data.records, data.current_page, data.total_pages);
                displayRecords(data.records);
                currentPage = data.current_page;
                totalPages = data.total_pages;
                updatePagination();
            } else {
                console.error("未找到记录或发生错误:", data);
                alert("未找到记录");
            }
        })
        .catch(error => {
            console.error("请求出错:", error);
            alert("请求失败，请稍后重试");
        });
}

// // 显示记录的函数
// function displayRecords(records) {
//     if (!Array.isArray(records)) {
//         console.error("Expected an array of records, but got:", records);
//         return;
//     }
//     const tableBody = document.getElementById("data-table");
//     tableBody.innerHTML = "";
//     records.forEach(record => {
//         // 确保 record 在这里定义
//         console.log(record);  // 调试查看 record 的内容
//         const row = document.createElement("tr");

//         // 设置操作按钮
//         let buttonHtml = '';
//         if (record.c_status === "1") {  // 判断 c_status 是否是字符串 '1'
//             buttonHtml = `<button onclick="handleSkip(${record.id})"style="background-color: #00cc66;">拦截</button>`;
//         } else if (record.c_status === "2") {
//             buttonHtml = `<button disabled style="background-color: grey;">拦截</button>`;
//         }

//         row.innerHTML = `
//             <td>${record.create_date}</td>
//             <td>${record.tel}</td>
//             <td>${record.zhanghu}</td>
//             <td>${record.huiyuanguize}</td>
//             <td><a href="#" onclick="showDetails(${record.id})">${record.r_status}</a></td>
//             <td>${buttonHtml}</td>
//         `;
//         tableBody.appendChild(row);
//     });
// }

// // 处理跳过按钮点击的函数
// function handleSkip(id) {
//     // 发起AJAX请求来检查和更新c_status
//     console.log('Sending request to skip ID:', id);
//     fetch(adminApi(`/api.php?action=check_and_update_c_status`), {
//         method: 'POST',
//         headers: {
//             'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({ id: id })
//     })
//     .then(response => {
//     if (!response.ok) {
//         throw new Error('Network response was not ok');
//     }
//     return response.json();
// })

//     //.then(response => response.json())
//     .then(data => {
//         console.log(data);  // 查看返回的数据结构
//         displayRecords(data);
//         if (data.success) {
//             alert("拦截成功");
//             // 重新加载数据，或更新页面中的按钮状态
//             loadRecords();
//         } else {
//             alert("拦截失败");
//         }
//     })
//     .catch(error => {
//         console.error('Error:', error);
//     });
// }
// console.log('Sending request to skip ID:');
// // 加载数据的函数
// function loadRecords() {
//     fetch('/getRecords')
//         .then(response => response.json())
//         .then(data => displayRecords(data))
//         .catch(error => console.error('Error:', error));
// }

// // 显示详情信息并隐藏列表
// function showDetails(id) {
//     fetch(adminApi(`/api.php?action=getDetails&id=${id}`))
//         .then(response => response.json())
//         .then(data => {
//             document.getElementById('details-info').innerText = data.details;
//             document.getElementById("data-table").style.display = 'none';
//             document.getElementById("details-container").style.display = 'block';
//         })
//         .catch(error => console.error('Error:', error));
// }

// // 返回列表页
// function goBack() {
//     document.getElementById("data-table").style.display = 'block';
//     document.getElementById("details-container").style.display = 'none';
// }

// // 更新分页显示
// function updatePagination() {
//     document.getElementById("pageInfo").innerText = `第 ${currentPage} 页`;
//     document.getElementById("prevPage").classList.toggle("disabled", currentPage <= 1);
//     document.getElementById("nextPage").classList.toggle("disabled", currentPage >= totalPages);
// }

// // 跳转到指定页
// function goToPage(page) {
//     if (page < 1 || page > totalPages) return;
//     fetchData('', page);
// }

// // 上一页/下一页翻页
// function changePage(offset) {
//     const newPage = currentPage + offset;
//     if (newPage < 1 || newPage > totalPages) return;
//     fetchData('', newPage);
// }



// 初始化加载第一页
fetchData();


