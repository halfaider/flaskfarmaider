const TASK_OPTS = [
    { value: TASK_KEYS[0], name: TASKS[TASK_KEYS[0]]['name'] },
    { value: TASK_KEYS[1], name: TASKS[TASK_KEYS[1]]['name'] },
    { value: TASK_KEYS[2], name: TASKS[TASK_KEYS[2]]['name'] },
    { value: TASK_KEYS[3], name: TASKS[TASK_KEYS[3]]['name'] },
    { value: TASK_KEYS[4], name: TASKS[TASK_KEYS[4]]['name'] },
    { value: TASK_KEYS[5], name: TASKS[TASK_KEYS[5]]['name'] },
];

const E_TASK = $('#sch-task');
const E_DESC = $('#sch-description');
const E_PATH = $('#sch-target-path');
const E_PATH_BTN = $('#sch-target-path-btn');
const E_TARGET_SECTION = $('#sch-target-section');
const E_RLCONE_REMOTE = $('#sch-rclone-remote');
const E_RECUR = $('#sch-recursive');
const E_SCAN_RADIO_0 = $('#sch-scan-mode0');
const E_SCAN_RADIO_1 = $('#sch-scan-mode1');
const E_CLEAR_SECTION = $('#sch-clear-section');
const E_CLEAR_RADIO_0 = $('#sch-clear-type0');
const E_CLEAR_RADIO_1 = $('#sch-clear-type1');
const E_CLEAR_RADIO_2 = $('#sch-clear-type2');
const E_CLEAR_LEVEL = $('#sch-clear-level');
const E_SCH_RADIO_0 = $('#sch-schedule-mode0');
const E_SCH_RADIO_1 = $('#sch-schedule-mode1');
const E_SCH_RADIO_2 = $('#sch-schedule-mode2');
const E_SCH_AUTO = $('#sch-schedule-auto-start');
const E_INTERVAL = $('#sch-schedule-interval');
const E_SAVE_BTN = $('#save-btn');
const E_MODAL_TITLE = $('#add-modal_title');
const E_MODAL = $('#add-modal')
const E_BROWSER_WD = $('#working-directory');
const E_BROWSER_WD_SUBMIT = $('#working-directory-submit');
const E_BROWSER_PARENT = $('#brw-list-table thead.dir-parent');
const E_BROWSER_TBODY = $('#brw-list-table tbody');
const E_GLOBAL_SEARCH_BTN = $('#globalSearchSearchBtn');
const E_SEARCH_RESET_BTN = $('#SearchResetBtn');
const E_GLOBAL_SEARCH_KEYWORD = $('#keyword');
const E_GLOBAL_SEARCH_ORDER = $('#order');
const E_GLOBAL_SEARCH_LENGTH = $('#length');
const E_GLOBAL_SEARCH_OPTION1 = $('#option1');
const E_GLOBAL_SEARCH_OPTION2 = $('#option2');
const E_SCH_LIST_TBODY = $('#sch-list-table tbody');

let remoteOptions = {};
for (let idx in SETTING_RCLONE_REMOTES) {
    remoteOptions[idx] = SETTING_RCLONE_REMOTES[idx];
}
let DEFAULT_CONTEXT_MENU_OPTIONS = {
    className: 'context-menu',
    autohide: true,
    callback: function(command, opt) {
        let path = opt.$trigger.data('path');
        confirmModal(TASKS[command].name + ' 작업을 실행할까요?', path, function() {
            let cmd = {
                command: command,
                path: path,
                recursive: opt.inputs['recursive'].$input.prop('checked'),
                scan_mode: opt.inputs['scan_mode'].$input.prop('value'),
                rclone_remote: opt.inputs['rclone_remote'].$input.prop('value'),
            }
            browserCommand(cmd);
        });
    },
    events: {
        show: function(opt) {
            console.log(opt.$trigger.data('path'));
        }
    },
    items: {
        [TASK_KEYS[0]]: {
            name: TASKS[TASK_KEYS[0]].name,
            icon: 'fa-refresh',
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        [TASK_KEYS[1]]: {
            name: TASKS[TASK_KEYS[1]].name,
            icon: 'fa-refresh',
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        [TASK_KEYS[2]]: {
            name: TASKS[TASK_KEYS[2]].name,
            icon: 'fa-search',
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        [TASK_KEYS[6]]: {
            name: TASKS[TASK_KEYS[6]].name,
            icon: 'fa-undo',
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        sep1: "---------",
        schedule: {
            name: '일정에 추가',
            icon: 'fa-plus',
            callback: function(key, opt, e) {
                path = $(this).data('path');
                openModal('browser', {target: path});
            },
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        clipboard: {
            name: '경로 복사',
            icon: 'fa-clipboard',
            callback: function(key, opt, e) {
                path = $(this).data('path');
                copyToClipboard(path);
            },
            disabled: function(){return $(this).hasClass('no-context');},
        },
        sep2: "---------",
        recursive: {
            name: 'Recursive',
            type: 'checkbox',
            selected: false,
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        rclone_remote: {
            name: '리모트 URL',
            type: 'select',
            options: remoteOptions,
            selected: 0,
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
        scan_mode: {
            name: '스캔 방식',
            type: 'select',
            options: {
                [SCAN_MODE_KEYS[0]]: SCAN_MODES[SCAN_MODE_KEYS[0]].name,
                [SCAN_MODE_KEYS[1]]: SCAN_MODES[SCAN_MODE_KEYS[1]].name,
            },
            selected: SCAN_MODE_KEYS[0],
            disabled: function(){return $(this).hasClass('restrict-context');},
        },
    },
}

function browserCommand(cmd) {
    let query = 'target=' + encodeURIComponent(cmd.path);
    query += '&rclone_remote=' + SETTING_RCLONE_REMOTES[cmd.rclone_remote];
    query += '&recursive=' + cmd.recursive;
    query += '&scan_mode=' + cmd.scan_mode;
    globalSendCommand(cmd.command, query, null, null, function(result) {
        if (result.ret == 'success' && cmd.command == 'list') {
            E_BROWSER_WD.prop('value', cmd.path);
            listDirectory(JSON.parse(result.data));
        }
    });
}

function listDirectory(result) {
    E_BROWSER_PARENT.empty();
    E_BROWSER_TBODY.empty();
    let linkClasses
    let nameIClasses = 'fa-folder pr-2';
    for (let index in result) {
        if (index == 0) {
            linkClasses = 'dir-folder no-context restrict-context';
            result[index].size = '';
            result[index].mtime = '';
        } else if (result[index].is_file) {
            linkClasses = 'dir-file restrict-context text-decoration-none font-weight-light';
            nameIClasses = 'fa-file pr-2';
        } else {
            linkClasses = 'dir-folder';
        }
        let tdName = '<td style="width: 60%" class="dir-btn browser-context-menu ' + linkClasses + '" data-path="' + result[index].path + '" role="button"><span href="#" class="dir-name pr-5' + linkClasses +'"><i class="fa fa-2 ' + nameIClasses + '" aria-hidden="true"></i>' + result[index].name + '</span></td>';
        let tdSize = '<td style="" class="text-right">' + result[index].size + '</td>';
        let tdMtime = '<td style="" class="text-center">' + result[index].mtime + '</td>';
        let tdButton = '<td style="" class="text-center"></td>';
        if (index != 0) {
            tdButton = '<td style="" class="text-center"><button class="btn browser-context-menu-btn dir-index-' + index + ' ' + linkClasses + '" data-path="' + result[index].path + '"><i class="fa fa-ellipsis-h fa-2x" aria-hidden="true"></i></button></td>';
        }
        let trGroup = '<tr class="dir-index-' + index + '">' + tdName + tdSize + tdMtime + tdButton + '</tr>';
        if (index == 0) {
            E_BROWSER_PARENT.append(trGroup);
        } else {
            E_BROWSER_TBODY.append(trGroup);
        }
    }
    $('.dir-btn').on('click', function (e) {
        // except file entries
        if ($(this).hasClass('dir-folder')) {
            let path = $(this).data('path');
            let cmd = {
                command: 'list',
                path: path,
                recursive: false,
                scan_mode: SCAN_MODE_KEYS[0],
            }
            browserCommand(cmd);
        }
    });
    // attach context menu
    let contextMenuTr = { ...DEFAULT_CONTEXT_MENU_OPTIONS };
    contextMenuTr.selector = '.browser-context-menu';
    $.contextMenu(contextMenuTr);
    let contextMenuBtn = { ...DEFAULT_CONTEXT_MENU_OPTIONS };
    contextMenuBtn.selector = '.browser-context-menu-btn'
    contextMenuBtn.trigger = 'left';
    $.contextMenu(contextMenuBtn);
}

// 일정 리스트 globalRequestSearch()@ff_global1.js 에서 make_list() 호출하기 때문에 구현
function make_list(data) {
    $('#select-all').prop('checked', false);
    $('#sch-list-table tbody').empty();
    for (let model of data){
        let colCheckbox = '<td class="text-center"><input type="checkbox" class="selectable" value="' + model.id + '"></td>';
        let colId = '<td class="text-center">' + model.id + '</td>';
        let colTask = '<td class="text-center">' + TASKS[model.task].name + '</td>';
        let colInterval = '<td class="text-center">' + (model.schedule_interval ? model.schedule_interval : '') + '</td>';
        let colTitle = '<td class="">' + (model.desc ? model.desc : '' )+ '</td>';
        let colSwitch
        if (model.schedule_mode == 'startup') {
            colSwitch = '<td class="text-center">' + FF_SCHEDULES[FF_SCHEDULE_KEYS[1]]['name'] + '</td>';
        } else {
            colSwitch = '<td class="text-center"><input id="sch-switch-' + model.id;
            colSwitch += '" type="checkbox" ' + ((model.is_include) ? 'checked' : '');
            colSwitch += ' class="sch-switch" data-toggle="toggle" data-size="xs" /></td>';
        }
        let colStatus = '<td class="text-center">' + ((model.status == STATUS_KEYS[1]) ? '<span class="text-warning status">실행중</span>' : '<span class="status">대기중</span>') + '</td>';
        let colFtime = '<td class="text-center">' + model.ftime + '</td>';

        let colManage = '<td class="text-center">';
        colManage += '<a href="#edit" class="sch-list-edit" title="편집"><i class="fa fa-lg fa-pencil-square-o" aria-hidden="true"></i></a>';
        colManage += '<a href="#delete" class="sch-list-delete mx-2 text-warning" title="삭제"><i class="fa fa-lg fa-trash" aria-hidden="true"></i></a>';
        colManage += '<a href="#execute" class="sch-list-execute text-info" title="지금 실행"><i class="fa fa-lg fa-play" aria-hidden="true"></i></a>';
        colManage += '</td>';

        let colScheduleMode = '<td class="text-center">';
        colScheduleMode += FF_SCHEDULES[model.schedule_mode]['name'];
        colScheduleMode += '</td>';

        let rowGroup = '<tr id="list-' + model.id + '" class="" data-id="'+ model.id +'" data-schedule_mode="' + model.schedule_mode + '">';
        rowGroup += colCheckbox + colId + colTask + colTitle + colStatus + colInterval + colFtime + colScheduleMode + colSwitch + colManage + '</tr>';
        E_SCH_LIST_TBODY.append(rowGroup);
    }
    // is_include 토글 활성화
    $('.sch-switch').bootstrapToggle();
    $('.sch-switch').on('change', function(e) {
        let mode = $(this).closest('tr').data('schedule_mode');
        if (mode == FF_SCHEDULE_KEYS[0]) {
            if ($(this).prop('checked')) {
                notify('활성화 할 수 없는 일정 방식입니다.', 'warning');
            }
            return
        }
        let id_ = $(this).closest('tr').data('id');
        let checked = $(this).prop('checked');
        globalSendCommand('schedule', 'id=' + id_ + '&active=' + checked, null, null, null);
    });
    // 관리 메뉴
    $('.sch-list-edit').on('click', function(e) {
        openModalById('edit', $(this).closest('tr').data('id'));
    });
    $('.sch-list-delete').on('click', function(e) {
        deleteModel($(this).closest('tr').data('id'));
    });
    $('.sch-list-execute').on('click', function(e) {
        exceuteSchedule($(this).closest('tr').data('id'));
    });
}

function toggleScheduleStatus(id, status) {
    let element = $('#list-' + id + ' span.status:first');
    if (status == STATUS_KEYS[0]) {
        element.prop('class', 'status');
        element.text('대기중');
    } else {
        element.prop('class', 'status text-warning');
        element.text('실행중');
    }
}

function disabledByScheduleMode(mode) {
    switch(mode) {
        case FF_SCHEDULE_KEYS[0]:
        case FF_SCHEDULE_KEYS[1]:
            E_INTERVAL.prop('disabled', true);
            E_SCH_AUTO.bootstrapToggle('off');
            E_SCH_AUTO.bootstrapToggle('disable');
            break;
        case FF_SCHEDULE_KEYS[2]:
            E_INTERVAL.prop('disabled', false);
            E_SCH_AUTO.bootstrapToggle('enable');
            break;
    }
}

function disabledByScanMode(mode) {
    switch(mode) {
        case SCAN_MODE_KEYS[0]:
        case SCAN_MODE_KEYS[1]:
            E_PATH.prop('disabled', false);
            E_PATH_BTN.prop('disabled', false);
            E_TARGET_SECTION.prop('disabled', false);
            break;
    }
}

function setClearLevel(type) {
    E_CLEAR_LEVEL.empty();
    E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start1').html('1단계'));
    switch(type) {
        case SECTION_TYPE_KEYS[0]:
        case SECTION_TYPE_KEYS[1]:
            if (type == SECTION_TYPE_KEYS[1]) {
                E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start21').html('2-1단계'));
                E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start22').html('2-2단계'));
            } else {
                E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start2').html('2단계'));
            }
            E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start3').html('3단계'));
            E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start4').html('4단계'));
            break;
        case SECTION_TYPE_KEYS[2]:
            E_CLEAR_LEVEL.append($('<option></option>').prop('value', 'start2').html('2단계'));
            break;
    }
    E_CLEAR_LEVEL.prop('value', '');
}

function exceuteSchedule(id_) {
    confirmModal('일정을 실행할까요?',
        'ID: ' + id_,
        function() {
            toggleScheduleStatus(id_, STATUS_KEYS[1]);
            globalSendCommand('execute', 'id=' + id_, null, null, null);
        }
    );
}

function openModal(from, data) {
    if (from == 'edit') {
        // 단일 편집
        setFormByTask(data.task);
        E_SAVE_BTN.data('id', [data.id]);
        E_TASK.prop('value', data.task);
        E_DESC.prop('value', data.desc);
        E_PATH.prop('value', data.target);
        E_RECUR.bootstrapToggle((data.recursive ? 'on' : 'off'));
        $('input[id^="sch-scan-mode"]:radio[value="' + data.scan_mode + '"]').prop('checked', true);
        disabledByScanMode(data.scan_mode);
        $('input[id^="sch-schedule-mode"]:radio[value="' + data.schedule_mode + '"]').prop('checked', true);
        disabledByScheduleMode(data.schedule_mode);
        E_INTERVAL.prop('value', data.schedule_interval);
        E_SCH_AUTO.bootstrapToggle((data.schedule_auto_start ? 'on' : 'off'));
        E_MODAL_TITLE.html('일정 편집 - ' + data.id);
        clear_type = data.clear_type ? data.clear_type : SECTION_TYPE_KEYS[0];
        $('input[id^="sch-clear-type"]:radio[value="' + clear_type + '"]').prop('checked', true);
        setClearLevel(clear_type);
        setPlexSections(clear_type, E_CLEAR_SECTION, SECTIONS);
        E_CLEAR_SECTION.prop('value', data.clear_section);
        E_CLEAR_LEVEL.prop('value', data.clear_level);
        E_TARGET_SECTION.prop('value', data.section_id);
        E_RLCONE_REMOTE.prop('value', data.rclone_remote);
        $('input[id$="-helper"][type="hidden"]').prop('checked', true);
    } else if (from == 'multiple-edit') {
        setFormByTask('multiple-edit');
        E_MODAL_TITLE.html('일정 일괄 편집 - ' + data);
        E_SAVE_BTN.data('id', data);
        E_TASK.prop('value', '');
        E_DESC.prop('value', '');
        E_PATH.prop('value', '');
        E_TARGET_SECTION.prop('value', '');
        E_INTERVAL.prop('value', '');
        $('input[id^="sch-scan-mode"]:radio').prop('checked', false);
        $('input[id^="sch-clear-type"]:radio').prop('checked', false);
        $('input[id^="sch-schedule-mode"]:radio').prop('checked', false);
        E_CLEAR_LEVEL.prop('value', '');
        E_CLEAR_SECTION.prop('value', '');
        E_RLCONE_REMOTE.prop('value', '');
        E_RECUR.bootstrapToggle('off');
        E_SCH_AUTO.bootstrapToggle('off');
        E_TASK.off('change');
        $('input[id^="sch-schedule-mode"]:radio').off('change');
        $('input[id$="-helper"][type="hidden"]').prop('checked', false);
    } else {
        // 새로 추가
        setFormByTask(TASK_KEYS[0]);
        E_TASK.prop('value', TASK_KEYS[0]);
        E_SAVE_BTN.data('id', [-1]);
        E_DESC.prop('value', '');
        if (from == 'browser') {
            // 브라우저에서 추가
            E_PATH.prop('value', data.target);
        } else {
            E_PATH.prop('value', '/');
        }
        E_RECUR.bootstrapToggle('off');
        E_SCAN_RADIO_0.prop('checked', true);
        E_SCH_RADIO_0.prop('checked', true);
        E_INTERVAL.prop('value', '');
        E_SCH_AUTO.bootstrapToggle('off');
        E_CLEAR_RADIO_0.prop('checked', true);
        E_TARGET_SECTION.prop('value', '');
        E_RLCONE_REMOTE.prop('value', '');
        disabledByScheduleMode(FF_SCHEDULE_KEYS[0]);
        disabledByScanMode(SCAN_MODE_KEYS[0]);
        setPlexSections(E_CLEAR_RADIO_0.prop('value'), E_CLEAR_SECTION, SECTIONS);
        setClearLevel(E_CLEAR_RADIO_0.prop('value'));
        E_MODAL_TITLE.html("일정 추가");
        $('input[id$="-helper"][type="hidden"]').prop('checked', true);
    }
    E_MODAL.modal({backdrop: 'static', keyboard: true}, 'show');
}

function setFormByTask(task) {
    E_TASK.prop('disabled', false);
    E_DESC.prop('disabled', false);
    E_PATH.prop('disabled', false);
    E_PATH_BTN.prop('disabled', false);
    E_TARGET_SECTION.prop('disabled', false);
    E_RLCONE_REMOTE.prop('disabled', false);
    E_RECUR.bootstrapToggle('enable');
    $('input[id^="sch-scan-mode"]:radio').prop('disabled', false);
    $('input[id^="sch-clear-type"]:radio').prop('disabled', false);
    $('input[id^="sch-schedule-mode"]:radio').prop('disabled', false);
    E_CLEAR_SECTION.prop('disabled', false);
    E_CLEAR_LEVEL.prop('disabled', false);
    E_INTERVAL.prop('disabled', false);
    E_SCH_AUTO.bootstrapToggle('enable');
    switch(task) {
        case TASK_KEYS[0]:
        case TASK_KEYS[1]:
        case TASK_KEYS[2]:
        case TASK_KEYS[3]:
        case TASK_KEYS[5]:
            $('input[id^="sch-clear-type"]:radio').prop('disabled', true);
            E_CLEAR_SECTION.prop('disabled', true);
            E_CLEAR_LEVEL.prop('disabled', true);
    }
    switch(task) {
        case TASK_KEYS[3]:
        case TASK_KEYS[4]:
        case TASK_KEYS[5]:
            E_PATH.prop('disabled', true);
            E_PATH_BTN.prop('disabled', true);
            E_TARGET_SECTION.prop('disabled', true);
    }
    switch(task) {
        case TASK_KEYS[2]:
        case TASK_KEYS[4]:
        case TASK_KEYS[5]:
            E_RLCONE_REMOTE.prop('disabled', true);
            E_RECUR.bootstrapToggle('off');
            E_RECUR.bootstrapToggle('disable');
    }
    switch(task) {
        case TASK_KEYS[1]:
        case TASK_KEYS[3]:
        case TASK_KEYS[4]:
        case TASK_KEYS[5]:
            $('input[id^="sch-scan-mode"]:radio').prop('disabled', true);
    }
    switch(task) {
        case TASK_KEYS[5]:
            E_SCH_RADIO_1.prop('checked', true);
            disabledByScheduleMode(FF_SCHEDULE_KEYS[1]);
            E_SCH_RADIO_0.prop('disabled', true);
            E_SCH_RADIO_2.prop('disabled', true);
            break;
    }
}

function setSearchOption2ByOption1(opt) {
    E_GLOBAL_SEARCH_OPTION2.empty();
    E_GLOBAL_SEARCH_OPTION2.append(
        $('<option></option>').prop('value', 'all').html('전체')
    );
    E_GLOBAL_SEARCH_KEYWORD.prop('disabled', false);
    switch(opt){
        case SEARCH_KEYS[0]:
            for (let idx in TASK_OPTS) {
                E_GLOBAL_SEARCH_OPTION2.append(
                    $('<option></option>').prop('value', TASK_OPTS[idx].value).html(TASK_OPTS[idx].name)
                );
            }
            E_GLOBAL_SEARCH_KEYWORD.prop('disabled', true);
            break;
        case SEARCH_KEYS[3]:
            for (let key in STATUSES){
                E_GLOBAL_SEARCH_OPTION2.append(
                    $('<option></option>').prop('value', key).html(STATUSES[key].name)
                );
            }
            E_GLOBAL_SEARCH_KEYWORD.prop('disabled', true);
            break;
    }
}

// 일정 업무 선택에 따라 inputs (비)활성화
E_TASK.on('change', function(e) {
    setFormByTask($(this).prop('value'));
});
E_PATH_BTN.on('click', function(e){
    e.preventDefault();
    let path = E_PATH.val().trim();
    if (path == '') path = '/';
    globalSelectLocalFile('경로 선택', path, function(result){
        E_PATH.val(result);
    });
});
if (SECTIONS) {
    for (let key in SECTIONS) {
        SECTIONS[key].forEach(function(item) {
            E_TARGET_SECTION.append(
                $('<option></option>').prop('value', item.id).append(item.name)
            );
        });
    }
}

// 스캔 방식에 따라 inputs (비)활성화
$('input[id^="sch-scan-mode"]:radio').change(function() {
    disabledByScanMode($(this).prop('value'));
});

// 라이브러리 타입에 따라 목록 변경
$('input[id^="sch-clear-type"]:radio').change(function() {
    setPlexSections($(this).prop('value'), E_CLEAR_SECTION, SECTIONS);
    setClearLevel($(this).prop('value'));
})

// 일정 방식 선택에 따라 inputs (비)활성화
$('input[id^="sch-schedule-mode"]:radio').change(function() {
    E_SCH_AUTO.bootstrapToggle('off');
    disabledByScheduleMode($(this).prop('value'));
});

E_MODAL.on('shown.bs.modal', function (e) {
});

E_MODAL.on('hidden.bs.modal', function (e) {
    E_TASK.on('change', function(e) {
        setFormByTask($(this).prop('value'));
    });
    $('input[id^="sch-schedule-mode"]:radio').change(function() {
        E_SCH_AUTO.bootstrapToggle('off');
        disabledByScheduleMode($(this).prop('value'));
    });
});

// 현재 디렉토리
E_BROWSER_WD.keypress(function(e) {
    if (e.keyCode && e.keyCode == 13) {
        E_BROWSER_WD_SUBMIT.trigger("click");
        return false;
    }
});

// 브라우저 이동 버튼
E_BROWSER_WD_SUBMIT.on('click', function(e) {
    let dir = E_BROWSER_WD.prop('value');
    browserCommand({command: 'list', path: dir, recursive: false, scan_mode: SCAN_MODE_KEYS[0]});
});

// 검색 inputs
E_GLOBAL_SEARCH_KEYWORD.keypress(function(e) {
    if (e.keyCode && e.keyCode == 13) {
        E_GLOBAL_SEARCH_BTN.trigger("click");
        return false;
    }
});

E_GLOBAL_SEARCH_LENGTH.on('change', function(e) {
    e.preventDefault();
    globalRequestSearch(1);
});

E_GLOBAL_SEARCH_OPTION1.change(function(){
    setSearchOption2ByOption1($(this).prop('value'));
});

// 초기 리스트 불러오기
// f'{order}|{page}|{page_size}|{keyword}|{option1}|{option2}'
E_GLOBAL_SEARCH_ORDER.prop('value', LAST_LIST_OPTIONS[0]);
E_GLOBAL_SEARCH_LENGTH.prop('value', LAST_LIST_OPTIONS[2]);
E_GLOBAL_SEARCH_KEYWORD.prop('value', LAST_LIST_OPTIONS[3]);
E_GLOBAL_SEARCH_OPTION1.prop('value', LAST_LIST_OPTIONS[4]);
setSearchOption2ByOption1(E_GLOBAL_SEARCH_OPTION1.prop('value'));
E_GLOBAL_SEARCH_OPTION2.prop('value', LAST_LIST_OPTIONS[5]);
globalRequestSearch(1);

// search reset button
E_SEARCH_RESET_BTN.on('click', function(e) {
    E_GLOBAL_SEARCH_LENGTH.prop('value', 10);
    E_GLOBAL_SEARCH_ORDER.prop('value', 'desc');
    E_GLOBAL_SEARCH_OPTION1.prop('value', SEARCH_KEYS[0]);
    setSearchOption2ByOption1(E_GLOBAL_SEARCH_OPTION1.prop('value'));
    E_GLOBAL_SEARCH_OPTION2.prop('value', 'all');
    E_GLOBAL_SEARCH_KEYWORD.prop('value', '');
    globalRequestSearch(1, false);
});

// 초기 디렉토리 불러오기
browserCommand({
    command: 'list',
    path: E_BROWSER_WD.prop('value'),
    recursive: false,
    scan_mode: SCAN_MODE_KEYS[0],
});

SOCKET.on('result', function(result) {
    if (result) {
        toggleScheduleStatus(result.data.id, result.data.status);
    }
});
