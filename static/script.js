"use strict";

/* Tags menu filter */

// 获取 HTML 中的标签名称到标签链接的字典
function getTags() {
  const tags = {}; // 初始化标签字典
  const list = document.querySelectorAll('.versions a'); // 获取所有 .versions 下的 a 标签
  for (const el of list) { // 遍历每个 a 标签
    tags[el.innerText.trim()] = el.href; // 将标签文本作为键，链接作为值存入字典
  }
  return tags; // 返回标签字典
}

// 根据输入生成标签搜索结果
// @param {string} filter - 当前过滤输入文本
// @param {Object} tags - 标签名到标签链接的字典
// @returns {DocumentFragment} 包含搜索结果的文档片段
function generateResults(filter, tags) {
  const searchResults = document.createDocumentFragment(); // 创建文档片段用于存储搜索结果
  const filterRegex = new RegExp(filter, 'i'); // 创建正则表达式用于匹配过滤文本

  for (let key in tags) { // 遍历标签字典
    if (tags.hasOwnProperty(key)) { // 检查键是否属于标签字典
      let tagFound = false; // 初始化标志变量，表示是否找到匹配项
      const tagHighlight = key.replace(filterRegex, result => { // 替换匹配项并高亮显示
        if (result) tagFound = true; // 如果找到匹配项，设置标志变量为 true
        return '<strong>' + result + '</strong>'; // 返回高亮显示的匹配项
      })

      if (tagFound) { // 如果找到匹配项
        const tagLink = document.createElement('a'); // 创建 a 标签元素
        tagLink.href = tags[key]; // 设置 a 标签的 href 属性
        tagLink.innerHTML = tagHighlight; // 设置 a 标签的 innerHTML
        searchResults.appendChild(tagLink); // 将 a 标签添加到文档片段
      }
    }
  }

  return searchResults; // 返回包含搜索结果的文档片段
}

// 设置标签过滤输入框
function setupVersionsFilter() {
  const input = document.querySelector('.filter-input'); // 获取过滤输入框
  const results = document.querySelector('.filter-results'); // 获取搜索结果显示区域
  const versions = document.querySelector('.versions'); // 获取版本列表
  const tags = getTags(); // 获取标签字典

  input.addEventListener('input', e => { // 监听输入事件
    if (e.target.value === '') { // 如果输入为空
      versions.classList.remove('hide'); // 显示版本列表
      results.innerHTML = ''; // 清空搜索结果显示区域
    } else { // 如果输入不为空
      versions.classList.add('hide'); // 隐藏版本列表
      results.innerHTML = ''; // 清空搜索结果显示区域
      results.appendChild(generateResults(e.target.value, tags)); // 生成并显示搜索结果
    }
  });
}

// 设置版本树的展开/折叠事件
function setupVersionsTree() {
  const versions = document.querySelector('.versions'); // 获取版本列表
  versions.addEventListener('click', e => { // 监听点击事件
    if (e.target && e.target.nodeName == 'SPAN') { // 如果点击的是 span 元素
      e.target.classList.toggle('active'); // 切换 active 类
    }
  });
}

// 检查当前布局是否为宽屏
function isWidescreen() {
  return getComputedStyle(document.documentElement).getPropertyValue('--is-widescreen') === 'true'; // 获取 CSS 变量 --is-widescreen 的值
}

// 切换侧边栏的可见性，处理宽屏和移动端布局
function toggleMenu() {
  const isWidescreen = getComputedStyle(document.documentElement).getPropertyValue('--is-widescreen') === 'true'; // 检查当前布局是否为宽屏
  if (isWidescreen) { // 如果是宽屏
    const hasShowMenu = document.documentElement.classList.contains('show-menu'); // 检查是否显示侧边栏
    window.localStorage.setItem('show-sidebar', !hasShowMenu); // 存储侧边栏状态
    document.documentElement.classList.toggle('show-menu'); // 切换侧边栏显示状态
  } else { // 如果是移动端
    document.documentElement.classList.toggle('show-menu-mobile'); // 切换移动端侧边栏显示状态
  }
}

// 设置侧边栏汉堡菜单按钮、关闭按钮和移动端侧边栏背景事件
function setupSidebarSwitch() {
  const tag = document.querySelector('.version em'); // 获取版本标签
  const openMenu = document.querySelector('.open-menu'); // 获取汉堡菜单按钮
  const sidebar = document.querySelector('.sidebar'); // 获取侧边栏

  // 在汉堡菜单按钮点击时切换侧边栏显示状态
  openMenu.addEventListener('click', e => {
    e.preventDefault(); // 阻止默认行为
    toggleMenu(); // 切换侧边栏显示状态
  });

  // 在版本标签点击时切换侧边栏显示状态
  tag.addEventListener('click', e => {
    e.preventDefault(); // 阻止默认行为
    toggleMenu(); // 切换侧边栏显示状态
  });

  // 在关闭按钮或侧边栏背景点击时关闭侧边栏
  sidebar.addEventListener('click', e => {
    if (e.target === sidebar && isWidescreen()) { // 如果点击的是侧边栏且是宽屏
      document.documentElement.classList.remove('show-menu'); // 关闭侧边栏
      window.localStorage.setItem('show-sidebar', false); // 存储侧边栏状态
    } else if (e.target === sidebar || e.target.classList.contains('close-menu')) { // 如果点击的是侧边栏或关闭按钮
      document.documentElement.classList.remove('show-menu-mobile'); // 关闭移动端侧边栏
    }
  });
}

// 解析 URL 哈希（锚点）格式 La-Lb，其中 a 和 b 是行号
// 高亮显示范围内的行号，并滚动到范围内的第一个行号
function handleLineRange(hashStr) {
  const hash = hashStr.substring(1).split("-"); // 解析哈希字符串
  if (hash.length != 2) { // 如果哈希格式不正确
    return; // 返回
  }

  const firstLineElement = document.getElementById(hash[0]); // 获取第一个行号元素
  const lastLineElement = document.getElementById(hash[1]); // 获取最后一个行号元素
  if (firstLineElement === undefined || lastLineElement === undefined) { // 如果行号元素不存在
    return; // 返回
  }

  highlightFromTo(firstLineElement, lastLineElement); // 高亮显示行号范围
  firstLineElement.scrollIntoView(); // 滚动到第一个行号
}

// 高亮显示从 firstLineElement 到 lastLineElement 的行号元素
function highlightFromTo(firstLineElement, lastLineElement) {
  let firstLine = parseInt(firstLineElement.id.substring(1)); // 获取第一个行号
  let lastLine = parseInt(lastLineElement.id.substring(1)); // 获取最后一个行号
  console.assert(!isNaN(firstLine) && !isNaN(lastLine), "Elements to highlight have invalid numbers in ids"); // 断言行号有效
  console.assert(firstLine < lastLine, "first highlight line is after last highlight line"); // 断言第一个行号在最后一个行号之前

  const firstCodeLine = document.getElementById(`codeline-${firstLine}`); // 获取第一个代码行元素
  const lastCodeLine = document.getElementById(`codeline-${lastLine}`); // 获取最后一个代码行元素

  addClassToRangeOfElements(firstLineElement.parentNode, lastLineElement.parentNode, "line-highlight"); // 为行号元素添加高亮类
  addClassToRangeOfElements(firstCodeLine, lastCodeLine, "line-highlight"); // 为代码行元素添加高亮类
}

// 为从 first 到 last 的元素添加指定类
function addClassToRangeOfElements(first, last, class_name) {
  let element = first; // 初始化元素
  const elementAfterLast = last !== null ? last.nextElementSibling : null; // 获取 last 元素的下一个兄弟元素
  while (element !== null && element != elementAfterLast) { // 遍历从 first 到 last 的元素
    element.classList.add(class_name); // 为元素添加指定类
    element = element.nextElementSibling; // 移动到下一个兄弟元素
  }
}

// 设置监听器以处理行号元素上的范围高亮显示
/**
 * 此函数为包含行号的元素设置监听器，以处理通过Shift键点击实现的范围高亮。
 */
function setupLineRangeHandlers() {
  // 检查页面是否包含行号元素
  // 如果不存在，则可能是脚本未在源页面上下文中执行
  const linenodiv = document.querySelector(".linenodiv");
  if (linenodiv === null) {
    return; // 如果未找到行号元素，直接返回
  }

  let rangeStart, rangeEnd; // 定义范围开始和结束的行号元素
  linenodiv.addEventListener("click", ev => {
    if (ev.ctrlKey || ev.metaKey) {
      return; // 如果按下了Ctrl或Meta键，忽略点击事件
    }
    ev.preventDefault(); // 阻止默认行为

    // 处理程序设置在包含所有行号的元素上，检查事件是否针对实际的行号元素
    const el = ev.target;
    if (typeof(el.id) !== "string" || el.id[0] !== "L" || el.tagName !== "A") {
      return; // 如果点击的目标不是行号元素，忽略点击事件
    }

    // 移除范围高亮
    const highlightElements = Array.from(document.getElementsByClassName("line-highlight"));
    for (let el of highlightElements) {
      el.classList.remove("line-highlight"); // 移除所有已有的高亮类
    }

    if (rangeStart === undefined || !ev.shiftKey) {
      rangeStart = el; // 设置范围开始行号元素
      rangeStart.classList.add("line-highlight"); // 添加高亮类
      rangeEnd = undefined; // 重置范围结束行号元素
      window.location.hash = rangeStart.id; // 更新URL哈希值
    } else if (ev.shiftKey) {
      if (rangeEnd === undefined) {
        rangeEnd = el; // 设置范围结束行号元素
      }

      let rangeStartNumber = parseInt(rangeStart.id.substring(1)); // 获取范围开始行号
      let rangeEndNumber = parseInt(rangeEnd.id.substring(1)); // 获取范围结束行号
      const elNumber = parseInt(el.id.substring(1)); // 获取当前点击行号
      console.assert(!isNaN(rangeStartNumber) && !isNaN(rangeEndNumber) && !isNaN(elNumber),
        "Elements to highlight have invalid numbers in ids"); // 断言行号有效

      // 交换范围元素以支持 "#L2-L1" 格式。遵循Postel定律
      if (rangeStartNumber > rangeEndNumber) {
        const rangeTmp = rangeStart;
        rangeStart = rangeEnd;
        rangeEnd = rangeTmp;

        const numberTmp = rangeStartNumber;
        rangeStartNumber = rangeEndNumber;
        rangeEndNumber = numberTmp;
      }

      if (elNumber < rangeStartNumber) {
        // 如果点击的行号在范围之上，扩展范围
        rangeStart = el;
      } else if (elNumber > rangeEndNumber) {
        // 如果点击的行号在范围之下，扩展范围
        rangeEnd = el;
      } else {
        // 如果点击的行号在范围内，调整最近的边界
        const distanceFromStart = Math.abs(rangeStartNumber - elNumber);
        const distanceFromEnd = Math.abs(rangeEndNumber - elNumber);
        if (distanceFromStart < distanceFromEnd) {
          rangeStart = el;
        } else if (distanceFromStart > distanceFromEnd) {
          rangeEnd = el;
        } else {
          rangeEnd = el;
        }
      }

      highlightFromTo(rangeStart, rangeEnd); // 高亮显示范围内的行
      window.location.hash = `${rangeStart.id}-${rangeEnd.id}`; // 更新URL哈希值
    }
  });
}

/* 其他修复 */

// 防止Chrome自动滚动到输入元素
function setupAutoscrollingPrevention() {
  const wrapper = document.querySelector('.wrapper'); // 获取包裹元素
  Array.prototype.forEach.call(document.querySelectorAll('input'), el => {
    el.addEventListener('keydown', _ => {
      const before = wrapper.scrollTop; // 记录滚动位置
      const reset = () => wrapper.scrollTop = before; // 重置滚动位置
      window.requestAnimationFrame(reset); // 请求动画帧
      setTimeout(reset, 0); // 延迟执行重置
    });
  });
}

// 在每次锚点变化后滚动页面，防止选中的行被顶部栏遮挡
function setupAnchorOffsetHandler() {
  const wrapper = document.querySelector('.wrapper'); // 获取包裹元素

  const anchorChangeHandler = e => {
    if (e && e.preventDefault) e.preventDefault(); // 阻止默认行为
    if (location.hash.length !== 0) {
      const el = document.querySelector(location.hash); // 获取锚点元素
      if (el) {
        const offsetTop = el.offsetTop; // 获取元素的偏移量
        wrapper.scrollTop = offsetTop < 100 ? 200 : offsetTop + 100; // 调整滚动位置
      }
    }
  };

  window.requestAnimationFrame(anchorChangeHandler); // 请求动画帧
  window.addEventListener('hashchange', anchorChangeHandler); // 监听哈希变化
}

// 设置回到顶部按钮
function setupGoToTop() {
  const wrapper = document.querySelector('.wrapper'); // 获取包裹元素
  const goToTop = document.querySelector('.go-top'); // 获取回到顶部按钮

  goToTop.addEventListener('click', e => {
    wrapper.scrollTop = 0; // 滚动到顶部
    wrapper.scrollLeft = 0; // 滚动到最左边
  });
}

// 修复错误的301重定向
// https://developer.mozilla.org/en-US/docs/Web/API/Request/cache
// https://developer.mozilla.org/en-US/docs/Web/API/Request/redirect
// TODO: 2024年10月后移除
function fix301() {
  let path = location.pathname.split('/'); // 分割路径
  if (path.length == 4) {
    path[2] = 'latest'; // 修改路径
    let newPath = path.join('/'); // 重新组合路径
    fetch(newPath, {
        cache: 'reload', // 强制重新加载
        redirect: 'manual', // 手动处理重定向
        // 这是为了确保Varnish将缓存响应，默认情况下fetch会在头中发送no-cache
        headers: {'Cache-Control': 'max-age=86400', 'Pragma': ''}
    })
      .then(console.log) // 成功时记录日志
      .catch(console.error); // 失败时记录错误
  }
}

document.addEventListener('DOMContentLoaded', _ => {
  setupVersionsFilter(); // 设置版本过滤器
  setupVersionsTree(); // 设置版本树
  setupSidebarSwitch(); // 设置侧边栏切换

  handleLineRange(window.location.hash); // 处理行范围
  setupLineRangeHandlers(); // 设置行范围处理器

  setupAutoscrollingPrevention(); // 设置自动滚动预防
  setupAnchorOffsetHandler(); // 设置锚点偏移处理器
  setupGoToTop(); // 设置回到顶部
  fix301(); // 修复301重定向
});
