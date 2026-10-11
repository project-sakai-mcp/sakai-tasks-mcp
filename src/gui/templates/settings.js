var globalCourses = [];
var saveTimer = null;

// 300ms デバウンス自動保存をスケジュール
function triggerAutoSave() {
  if (saveTimer) {
    clearTimeout(saveTimer);
  }
  saveTimer = setTimeout(function() {
    performSave();
  }, 300);
}

function performSave() {
  var sakaiHost = document.getElementById('sakai-host').value.trim();
  var deadlineDays = parseInt(document.getElementById('default-deadline-days').value, 10);
  if (isNaN(deadlineDays) || deadlineDays <= 0) {
    deadlineDays = 30;
  }

  var announcementLimit = parseInt(document.getElementById('default-announcement-limit').value, 10);
  if (isNaN(announcementLimit) || announcementLimit <= 0) {
    announcementLimit = 7;
  }

  var updatedCourses = [];
  globalCourses.forEach(function(course) {
    var selected = document.querySelector('input[name="policy_' + course.id + '"]:checked');
    var policyVal = selected ? selected.value : course.current_policy;
    updatedCourses.push({
      id: course.id,
      title: course.title,
      is_favorite: course.is_favorite,
      current_policy: policyVal
    });
  });

  var payload = {
    sakai_host: sakaiHost,
    default_deadline_days: deadlineDays,
    default_announcement_limit: announcementLimit,
    courses: updatedCourses
  };

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.save_settings(payload).catch(function(err) {
      console.error('Save error:', err);
    });
  }
}

function init() {
  if (window.pywebview && window.pywebview.api) {
    loadData();
  } else {
    window.addEventListener('pywebviewready', loadData);
  }
}

function loadData() {
  window.pywebview.api.get_initial_data().then(function(data) {
    renderUI(data);
  });
}

function renderUI(data) {
  // 1. ドメイン設定
  var hostInput = document.getElementById('sakai-host');
  var presetSelect = document.getElementById('preset-select');
  hostInput.value = data.sakai_host;

  for (var name in data.presets) {
    var opt = document.createElement('option');
    opt.value = data.presets[name];
    opt.textContent = name;
    if (data.presets[name] === data.sakai_host) {
      opt.selected = true;
    }
    presetSelect.appendChild(opt);
  }

  hostInput.addEventListener('input', triggerAutoSave);

  presetSelect.addEventListener('change', function() {
    if (presetSelect.value) {
      hostInput.value = presetSelect.value;
      triggerAutoSave();
    }
  });

  // 6. 詳細パラメータ
  var deadlineDaysInput = document.getElementById('default-deadline-days');
  deadlineDaysInput.value = data.default_deadline_days;
  deadlineDaysInput.addEventListener('input', triggerAutoSave);
  deadlineDaysInput.addEventListener('change', triggerAutoSave);

  var announcementLimitInput = document.getElementById('default-announcement-limit');
  announcementLimitInput.value = data.default_announcement_limit;
  announcementLimitInput.addEventListener('input', triggerAutoSave);
  announcementLimitInput.addEventListener('change', triggerAutoSave);

  // 5. 講義一覧 (お気に入りとその他に分離)
  globalCourses = data.courses || [];
  var tbody = document.getElementById('courses-tbody');
  var coursesTable = document.getElementById('courses-table');
  var searchContainer = document.getElementById('search-container');
  var emptyNotice = document.getElementById('empty-courses-notice');

  tbody.innerHTML = '';

  if (globalCourses.length === 0) {
    coursesTable.style.display = 'none';
    searchContainer.style.display = 'none';
    emptyNotice.style.display = 'block';
    return;
  } else {
    coursesTable.style.display = '';
    searchContainer.style.display = '';
    emptyNotice.style.display = 'none';
  }

  var policies = ['allow_all', 'text_only', 'schedule_only', 'blocked'];
  var favCourses = globalCourses.filter(function(c) { return c.is_favorite; });
  var otherCourses = globalCourses.filter(function(c) { return !c.is_favorite; });

  var otherRowsCollapsed = true;

  function createCourseRow(course, isFav) {
    var tr = document.createElement('tr');
    tr.dataset.courseId = course.id;
    tr.dataset.courseTitle = course.title.toLowerCase();
    tr.dataset.isFavorite = isFav ? "true" : "false";

    // 講義名セル
    var tdTitle = document.createElement('td');
    var prefix = isFav ? '★ ' : '  ';
    tdTitle.textContent = prefix + course.title;
    tr.appendChild(tdTitle);

    // 各ポリシーのラジオボタン
    policies.forEach(function(pol) {
      var tdRadio = document.createElement('td');
      tdRadio.style.textAlign = 'center';
      var radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'policy_' + course.id;
      radio.value = pol;
      if (course.current_policy === pol) {
        radio.checked = true;
      }
      radio.addEventListener('change', function() {
        updateBatchRadioState();
        triggerAutoSave();
      });
      tdRadio.appendChild(radio);
      tr.appendChild(tdRadio);
    });

    return tr;
  }

  // お気に入り講義を描画
  favCourses.forEach(function(course) {
    tbody.appendChild(createCourseRow(course, true));
  });

  // お気に入り以外の講義が存在する場合、トグル見出し行と各講義行を追加
  if (otherCourses.length > 0) {
    var toggleTr = document.createElement('tr');
    toggleTr.id = 'other-courses-header-row';
    toggleTr.style.backgroundColor = '#f0f0f0';
    toggleTr.style.cursor = 'pointer';
    toggleTr.style.userSelect = 'none';

    var toggleTd = document.createElement('td');
    toggleTd.colSpan = 5;
    toggleTd.style.fontSize = '13px';
    toggleTd.style.color = '#3d3d3d';
    function updateToggleText() {
      toggleTd.textContent = 'お気に入り以外の講義 (' + otherCourses.length + ' 件) を' + (otherRowsCollapsed ? '表示...' : '非表示');
    }
    updateToggleText();

    toggleTr.appendChild(toggleTd);
    tbody.appendChild(toggleTr);

    otherCourses.forEach(function(course) {
      var tr = createCourseRow(course, false);
      tr.className = 'other-course-row';
      tr.style.display = otherRowsCollapsed ? 'none' : '';
      tbody.appendChild(tr);
    });

    toggleTr.addEventListener('click', function() {
      otherRowsCollapsed = !otherRowsCollapsed;
      updateToggleText();
      var otherRows = document.querySelectorAll('.other-course-row');
      var query = document.getElementById('search-box').value.toLowerCase().trim();
      otherRows.forEach(function(row) {
        if (otherRowsCollapsed) {
          row.style.display = 'none';
        } else {
          var title = row.dataset.courseTitle;
          row.style.display = (query === '' || title.indexOf(query) !== -1) ? '' : 'none';
        }
      });
    });
  }

  updateBatchRadioState();
}

// 3. 一括適用ラジオボタン
function setAllPolicies(policyValue) {
  var radios = document.querySelectorAll('#courses-tbody input[type="radio"][value="' + policyValue + '"]');
  radios.forEach(function(radio) {
    radio.checked = true;
  });
  updateBatchRadioState();
  triggerAutoSave();
}

// 各講義の選択状態をもとに、全行一致していればヘッダーの丸ボタンをONにする
function updateBatchRadioState() {
  var policies = [
    { id: 'btn-all-allow', value: 'allow_all' },
    { id: 'btn-all-text', value: 'text_only' },
    { id: 'btn-all-schedule', value: 'schedule_only' },
    { id: 'btn-all-blocked', value: 'blocked' }
  ];

  var totalRows = globalCourses.length;
  if (totalRows === 0) return;

  policies.forEach(function(item) {
    var checkedCount = document.querySelectorAll('#courses-tbody input[type="radio"][value="' + item.value + '"]:checked').length;
    var headerRadio = document.getElementById(item.id);
    if (headerRadio) {
      headerRadio.checked = (checkedCount === totalRows);
    }
  });
}

document.getElementById('btn-all-allow').addEventListener('change', function() { setAllPolicies('allow_all'); });
document.getElementById('btn-all-text').addEventListener('change', function() { setAllPolicies('text_only'); });
document.getElementById('btn-all-schedule').addEventListener('change', function() { setAllPolicies('schedule_only'); });
document.getElementById('btn-all-blocked').addEventListener('change', function() { setAllPolicies('blocked'); });

// 4. 講義絞り込み検索 (検索時は該当する行を自動展開して表示)
document.getElementById('search-box').addEventListener('input', function() {
  var query = this.value.toLowerCase().trim();
  var rows = document.querySelectorAll('#courses-tbody tr[data-course-id]');
  var toggleRow = document.getElementById('other-courses-header-row');

  if (query !== '') {
    // 検索文字列があるときは一致した行をすべて表示
    if (toggleRow) toggleRow.style.display = 'none';
    rows.forEach(function(row) {
      var title = row.dataset.courseTitle;
      if (title.indexOf(query) !== -1) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  } else {
    // 検索がクリアされたら折りたたみ状態を復元
    if (toggleRow) toggleRow.style.display = '';
    rows.forEach(function(row) {
      if (row.dataset.isFavorite === 'true') {
        row.style.display = '';
      } else {
        row.style.display = (document.getElementById('other-courses-header-row') && !row.classList.contains('other-course-row')) ? '' : (row.style.display = (toggleRow && toggleRow.textContent.indexOf('非表示') !== -1 ? '' : 'none'));
      }
    });
  }
});

window.addEventListener('DOMContentLoaded', init);
