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
    updatedCourses.push({
      id: course.id,
      title: course.title,
      is_favorite: course.is_favorite,
      current_policy: course.current_policy
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
  // 1. ドメイン設定 (カスタムサジェスト)
  var hostInput = document.getElementById('sakai-host');
  var suggestList = document.getElementById('suggest-list');
  hostInput.value = data.sakai_host;

  function renderSuggestItems(filterText) {
    suggestList.innerHTML = '';
    var query = (filterText || '').toLowerCase().trim();
    var count = 0;

    for (var name in data.presets) {
      var host = data.presets[name];
      if (!query || name.toLowerCase().indexOf(query) !== -1 || host.toLowerCase().indexOf(query) !== -1) {
        var li = document.createElement('li');
        li.className = 'suggest-item';
        li.dataset.host = host;

        var nameSpan = document.createElement('span');
        nameSpan.className = 'suggest-item-name';
        nameSpan.textContent = name;

        var hostSpan = document.createElement('span');
        hostSpan.className = 'suggest-item-host';
        hostSpan.textContent = host;

        li.appendChild(nameSpan);
        li.appendChild(hostSpan);

        li.addEventListener('mousedown', function(e) {
          e.preventDefault();
          hostInput.value = this.dataset.host;
          suggestList.style.display = 'none';
          triggerAutoSave();
        });

        suggestList.appendChild(li);
        count++;
      }
    }

    suggestList.style.display = count > 0 ? 'block' : 'none';
  }

  hostInput.addEventListener('focus', function() {
    renderSuggestItems(hostInput.value);
  });

  hostInput.addEventListener('input', function() {
    renderSuggestItems(hostInput.value);
    triggerAutoSave();
  });

  hostInput.addEventListener('blur', function() {
    suggestList.style.display = 'none';
  });

  // AI権限の説明トグル
  var togglePolicyDescBtn = document.getElementById('toggle-policy-desc');
  var policyDescBox = document.getElementById('policy-desc-box');
  if (togglePolicyDescBtn && policyDescBox) {
    togglePolicyDescBtn.addEventListener('click', function() {
      var isHidden = policyDescBox.style.display === 'none';
      policyDescBox.style.display = isHidden ? 'block' : 'none';
      togglePolicyDescBtn.textContent = isHidden ? '詳細を非表示' : '詳細を表示';
    });
  }

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
  var coursesList = document.getElementById('courses-list');
  var coursesContainer = document.getElementById('courses-container');
  var emptyNotice = document.getElementById('empty-courses-notice');
  var batchSelect = document.getElementById('batch-select');

  coursesList.innerHTML = '';

  if (globalCourses.length === 0) {
    coursesContainer.style.display = 'none';
    emptyNotice.style.display = 'block';
    return;
  } else {
    coursesContainer.style.display = '';
    emptyNotice.style.display = 'none';
  }

  var policyOptions = [
    { value: 'allow_all', label: '全て' },
    { value: 'text_only', label: '強' },
    { value: 'schedule_only', label: '弱' },
    { value: 'blocked', label: '無効' }
  ];

  var favCourses = globalCourses.filter(function(c) { return c.is_favorite; });
  var otherCourses = globalCourses.filter(function(c) { return !c.is_favorite; });
  var otherRowsCollapsed = true;

  function createCourseRow(course, isFav) {
    var row = document.createElement('div');
    row.className = 'course-row';
    row.dataset.courseId = course.id;
    row.dataset.courseTitle = course.title.toLowerCase();
    row.dataset.isFavorite = isFav ? "true" : "false";

    // 左側: 講義名
    var info = document.createElement('div');
    info.className = 'course-info';

    var star = document.createElement('span');
    star.className = 'course-star';
    star.textContent = isFav ? '★ ' : '　';
    info.appendChild(star);

    var titleSpan = document.createElement('span');
    titleSpan.textContent = course.title;
    info.appendChild(titleSpan);

    row.appendChild(info);

    // 右側: 4分割セグメントコントロール
    var segmentGroup = document.createElement('div');
    segmentGroup.className = 'segmented-control';

    policyOptions.forEach(function(opt) {
      var btn = document.createElement('div');
      btn.className = 'segment-btn' + (course.current_policy === opt.value ? ' active' : '');
      btn.textContent = opt.label;
      btn.dataset.value = opt.value;

      btn.addEventListener('click', function() {
        if (course.current_policy === opt.value) return;
        course.current_policy = opt.value;

        // active クラスの切り替え
        var siblings = segmentGroup.querySelectorAll('.segment-btn');
        siblings.forEach(function(s) { s.classList.remove('active'); });
        btn.classList.add('active');

        triggerAutoSave();
      });

      segmentGroup.appendChild(btn);
    });

    row.appendChild(segmentGroup);
    return row;
  }

  // お気に入り講義を描画
  favCourses.forEach(function(course) {
    coursesList.appendChild(createCourseRow(course, true));
  });

  // お気に入り以外の講義が存在する場合
  if (otherCourses.length > 0) {
    var toggleBtn = document.createElement('div');
    toggleBtn.id = 'toggle-other-courses';
    toggleBtn.className = 'toggle-other-courses';

    function updateToggleText() {
      toggleBtn.textContent = 'お気に入り以外の講義 (' + otherCourses.length + '件) を' + (otherRowsCollapsed ? '表示' : '非表示');
    }
    updateToggleText();

    otherCourses.forEach(function(course) {
      var row = createCourseRow(course, false);
      row.classList.add('other-course-row');
      row.style.display = otherRowsCollapsed ? 'none' : '';
      coursesList.appendChild(row);
    });

    // 折りたたみ時も展開時も、表示されている講義群の末尾に配置する
    coursesList.appendChild(toggleBtn);

    toggleBtn.addEventListener('click', function() {
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
      // 常に末尾（全講義の下）へ移動
      coursesList.appendChild(toggleBtn);
    });
  }

  // 一括設定ドロップダウン (選択されたポリシーにすべて変更するシンプルな仕様)
  batchSelect.addEventListener('change', function() {
    var val = batchSelect.value;
    if (!val) return;

    globalCourses.forEach(function(c) {
      c.current_policy = val;
    });

    // すべてのセグメントボタンを更新
    var allRows = document.querySelectorAll('.course-row');
    allRows.forEach(function(row) {
      var btns = row.querySelectorAll('.segment-btn');
      btns.forEach(function(btn) {
        if (btn.dataset.value === val) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    });

    // 実行後は次の選択に備えて初期表示に戻す
    batchSelect.value = '';

    triggerAutoSave();
  });

  // 講義絞り込み検索
  document.getElementById('search-box').addEventListener('input', function() {
    var query = this.value.toLowerCase().trim();
    var rows = document.querySelectorAll('.course-row');
    var toggleElem = document.getElementById('toggle-other-courses');

    if (query !== '') {
      if (toggleElem) toggleElem.style.display = 'none';
      rows.forEach(function(row) {
        var title = row.dataset.courseTitle;
        row.style.display = (title.indexOf(query) !== -1) ? '' : 'none';
      });
    } else {
      if (toggleElem) toggleElem.style.display = '';
      rows.forEach(function(row) {
        if (row.dataset.isFavorite === 'true') {
          row.style.display = '';
        } else {
          row.style.display = otherRowsCollapsed ? 'none' : '';
        }
      });
    }
  });
}

window.addEventListener('DOMContentLoaded', init);

