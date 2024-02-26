const TASK_OPTS = [
    { value: TASK_KEYS[0], name: TASKS[TASK_KEYS[0]]['name'] },
    { value: TASK_KEYS[1], name: TASKS[TASK_KEYS[1]]['name'] },
    { value: TASK_KEYS[2], name: TASKS[TASK_KEYS[2]]['name'] },
    { value: TASK_KEYS[3], name: TASKS[TASK_KEYS[3]]['name'] },
    { value: TASK_KEYS[4], name: TASKS[TASK_KEYS[4]]['name'] },
    { value: TASK_KEYS[5], name: TASKS[TASK_KEYS[5]]['name'] },
];
const SCAN_OPTS = [
    { value: SCAN_MODE_KEYS[0], name: SCAN_MODES[SCAN_MODE_KEYS[0]]['name'] },
    { value: SCAN_MODE_KEYS[1], name: SCAN_MODES[SCAN_MODE_KEYS[1]]['name'] },
    { value: SCAN_MODE_KEYS[2], name: SCAN_MODES[SCAN_MODE_KEYS[2]]['name'] },
];
const CLEAR_OPTS = [
    { value: SECTION_TYPE_KEYS[0], name: SECTION_TYPES[SECTION_TYPE_KEYS[0]]['name'] },
    { value: SECTION_TYPE_KEYS[1], name: SECTION_TYPES[SECTION_TYPE_KEYS[1]]['name'] },
    { value: SECTION_TYPE_KEYS[2], name: SECTION_TYPES[SECTION_TYPE_KEYS[2]]['name'] },
];
const SCHEDULE_OPTS = [
    { value: FF_SCHEDULE_KEYS[0], name: FF_SCHEDULES[FF_SCHEDULE_KEYS[0]]['name'] },
    { value: FF_SCHEDULE_KEYS[1], name: FF_SCHEDULES[FF_SCHEDULE_KEYS[1]]['name'] },
    { value: FF_SCHEDULE_KEYS[2], name: FF_SCHEDULES[FF_SCHEDULE_KEYS[2]]['name'] },
];
const SEARCH_OPTS = [
    { value: SEARCH_KEYS[0], name: SEARCHES[SEARCH_KEYS[0]]['name'] },
    { value: SEARCH_KEYS[1], name: SEARCHES[SEARCH_KEYS[1]]['name'] },
    { value: SEARCH_KEYS[2], name: SEARCHES[SEARCH_KEYS[2]]['name'] },
    { value: SEARCH_KEYS[3], name: SEARCHES[SEARCH_KEYS[3]]['name'] },
    { value: SEARCH_KEYS[4], name: SEARCHES[SEARCH_KEYS[4]]['name'] },
]

function browser_command(cmd) {
    let query = 'target=' + cmd.path;
    query += '&vfs=' + cmd.vfs;
    query += '&recursive=' + cmd.recursive;
    query += '&scan_mode=' + cmd.scan_mode;
    query += '&periodic_id=-1';

    globalSendCommand(cmd.command, query, null, null, function(result) {
        if (result.ret == 'success' && cmd.command == 'list') {
            E_BROWSER_WD.prop('value', cmd.path);
            list_dir(JSON.parse(result.data));
        }
    });
}

function list_dir(result) {
    E_BROWSER_PARENT.empty();
    E_BROWSER_TBODY.empty();
    let link_classes
    let name_i_classes = 'fa-folder pr-2';
    for (let index in result) {
        if (index == 0) {
            link_classes = 'dir-folder no-context restrict-context';
            result[index].size = '';
            result[index].mtime = '';
        } else if (result[index].is_file) {
            link_classes = 'dir-file restrict-context text-decoration-none font-weight-light';
            name_i_classes = 'fa-file pr-2';
        } else {
            link_classes = 'dir-folder';
        }
        let td_name = '<td class="pl-3 w-75"><span href="#" class="dir-name pr-5' + link_classes +'"><i class="fa fa-2 ' + name_i_classes + '" aria-hidden="true"></i>' + result[index].name + '</span></td>';
        let td_size = '<td class="text-right">' + result[index].size + '</td>';
        let td_mtime = '<td class="text-center">' + result[index].mtime + '</td></tr>';
        let tr_group = '<tr role="button" data-path="' + result[index].path + '" class="dir-btn browser-context-menu btn-neutral dir-index-' + index + ' ' + link_classes + '">' + td_name + td_size + td_mtime + '</tr>';
        if (index == 0) {
            E_BROWSER_PARENT.append(tr_group);
        } else {
            E_BROWSER_TBODY.append(tr_group);
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
                vfs: VFS,
                scan_mode: SCAN_MODE_KEYS[0],
            }
            browser_command(cmd);
        }
    });
    // attach context menu
    let vfs_options = {};
    for (let idx in _VFSES) {
        vfs_options[_VFSES[idx]] = _VFSES[idx];
    }
    $.contextMenu({
        selector: '.browser-context-menu',
        className: 'context-menu',
        autohide: true,
        callback: function(command, opt) {
            let path = opt.$trigger.data('path');
            confirm_modal(TASKS[command].name + ' 작업을 실행할까요?', path, function() {
                let cmd = {
                    command: command,
                    path: path,
                    recursive: opt.inputs['recursive'].$input.prop('checked'),
                    scan_mode: opt.inputs['scan_mode'].$input.prop('value'),
                    vfs: opt.inputs['vfs'].$input.prop('value'),
                }
                browser_command(cmd);
            });
        },
        events: {
            show: function(opt) {
                // console.log(opt.$trigger.data('path'));
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
                    schedule_modal('browser', {target: path});
                },
                disabled: function(){return $(this).hasClass('restrict-context');},
            },
            clipboard: {
                name: '경로 복사',
                icon: 'fa-clipboard',
                callback: function(key, opt, e) {
                    path = $(this).data('path');
                    copy_to_clipboard(path);
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
            vfs: {
                name: 'vfs 리모트',
                type: 'select',
                options: vfs_options,
                selected: VFS,
                disabled: function(){return $(this).hasClass('restrict-context');},
            },
            scan_mode: {
                name: '스캔 방식',
                type: 'select',
                options: {
                    [SCAN_MODE_KEYS[2]]: SCAN_MODES[SCAN_MODE_KEYS[2]].name,
                    [SCAN_MODE_KEYS[0]]: SCAN_MODES[SCAN_MODE_KEYS[0]].name,
                },
                selected: SCAN_MODE_KEYS[2],
                disabled: function(){return $(this).hasClass('restrict-context');},
            },
        },
    });
}

// 일정 리스트 globalRequestSearch()@ff_global1.js 에서 make_list() 호출하기 때문에 구현
function make_list(data) {
    $('#select-all').prop('checked', false);
    $('#sch-list-table tbody').empty();
    for (let model of data){
        let col_checkbox = '<td class="text-center"><input type="checkbox" class="selectable" value="' + model.id + '"></td>';
        let col_id = '<td class="text-center">' + model.id + '</td>';
        let col_task = '<td class="text-center">' + TASKS[model.task].name + '</td>';
        let col_interval = '<td class="text-center">' + model.schedule_interval + '</td>';
        let col_title = '<td class="">' + model.desc + '</td>';
        let col_switch
        if (model.schedule_mode == 'startup') {
            col_switch = '<td class="text-center">' + FF_SCHEDULES[FF_SCHEDULE_KEYS[1]]['name'] + '</td>';
        } else {
            col_switch = '<td class="text-center"><input id="sch-switch-' + model.id;
            col_switch += '" data-id="' + model.id;
            col_switch += '" data-schedule_mode="' + model.schedule_mode;
            col_switch += '" type="checkbox" ' + ((model.is_include) ? 'checked' : '');
            col_switch += ' data-toggle="toggle" class="sch-switch" /></td>';
        }
        let col_status = '<td class="text-center">' + ((model.status == STATUS_KEYS[1]) ? '<span class="text-warning status">실행중</span>' : '<span class="status">대기중</span>') + '</td>';
        let col_ftime = '<td class="text-center">' + model.ftime + '</td>';

        let col_manage = '<td class="text-center">';
        col_manage += '<a href="#edit" class="sch-list-edit" data-id="' + model.id + '" title="편집"><i class="fa fa-lg fa-pencil-square-o" aria-hidden="true"></i></a>';
        col_manage += '<a href="#delete" class="sch-list-delete mx-2 text-warning" data-id="' + model.id + '" title="삭제"><i class="fa fa-lg fa-trash" aria-hidden="true"></i></a>';
        col_manage += '<a href="#execute" class="sch-list-execute text-info" data-id="' + model.id + '" title="지금 실행"><i class="fa fa-lg fa-play" aria-hidden="true"></i></a>';
        col_manage += '</td>';

        let col_schedule_mode = '<td class="text-center">';
        col_schedule_mode += FF_SCHEDULES[model.schedule_mode]['name'];
        col_schedule_mode += '</td>';

        let row_sub = '<tr><td colspan="8" class="p-0"><div id="collapse-' + model.id;
        row_sub += '" class="collapse hide" aria-labelledby="list-' + model.id;
        row_sub += '" data-parent="#sch-accordion"><div class="">';
        row_sub += '';
        row_sub += '</div></div></td></tr>';
        let row_group = '<tr id="list-' + model.id + '" class="" data-toggle="collapse" data-target="#collapse-' + model.id;
        row_group += '" aria-expanded="true" aria-controls="collapse-' + model.id + '">';
        row_group += col_checkbox + col_id + col_task + col_title + col_status + col_interval + col_ftime + col_schedule_mode + col_switch + col_manage + '</tr>' + row_sub;
        E_SCH_LIST_TBODY.append(row_group);
    }
    // is_include 토글 활성화
    $('.sch-switch').bootstrapToggle();
    $('.sch-switch').on('change', function(e) {
        let mode = $(this).data('schedule_mode');
        if (mode == FF_SCHEDULE_KEYS[0]) {
            if ($(this).prop('checked')) {
                notify('활성화 할 수 없는 일정 방식입니다.', 'warning');
                $(this).bootstrapToggle('off');
            }
            return
        }
        let _id = $(this).data('id');
        let checked = $(this).prop('checked');
        globalSendCommand('schedule', 'id=' + _id + '&active=' + checked, null, null, null);
    });
    $('.sch-switch ~ div.toggle-group').on('click', function(e) {
        // collapse까지 bubble up 되는 것 방지
        e.stopPropagation();
        $(this).prev().bootstrapToggle('toggle');
    })
    // 관리 메뉴
    $('.sch-list-edit').on('click', function(e) {
        schedule_modal_by_id('edit', $(this).data('id'));
    });
    $('.sch-list-delete').on('click', function(e) {
        delete_job($(this).data('id'));
    });
    $('.sch-list-execute').on('click', function(e) {
        execute_job($(this).data('id'));
    });
}

function toggle_schedule_status(id, status) {
    let element = $('#list-' + id + ' span.status:first');
    if (status == STATUS_KEYS[0]) {
        element.prop('class', 'status');
        element.text('대기중');
    } else {
        element.prop('class', 'status text-warning');
        element.text('실행중');
    }
}

function disabled_by_schedule_mode(mode) {
    switch(mode) {
        case FF_SCHEDULE_KEYS[0]:
        case FF_SCHEDULE_KEYS[1]:
            E_INTERVAL.prop('disabled', true);
            E_SCH_AUTO.bootstrapToggle('off');
            E_SCH_AUTO.bootstrapToggle('disable');
            E_SCH_AUTO_SEL.prop('value', '');
            break;
        case FF_SCHEDULE_KEYS[2]:
            E_INTERVAL.prop('disabled', false);
            E_SCH_AUTO.bootstrapToggle('enable');
            E_SCH_AUTO_SEL.prop('value', '');
            break;
    }
}

function disabled_by_scan_mode(mode) {
    switch(mode) {
        case SCAN_MODE_KEYS[0]:
        case SCAN_MODE_KEYS[2]:
            E_PATH.prop('disabled', false);
            E_PATH_BTN.prop('disabled', false);
            E_TARGET_SECTION.prop('disabled', false);
            E_SCAN_PERIODIC_ID.prop('disabled', true);
            break;
        case SCAN_MODE_KEYS[1]:
            E_PATH.prop('disabled', true);
            E_PATH_BTN.prop('disabled', true);
            E_TARGET_SECTION.prop('disabled', true);
            E_SCAN_PERIODIC_ID.prop('disabled', false);
            break;
    }
}

function set_clear_level(type) {
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

function execute_job(job_id) {
    confirm_modal('일정을 실행할까요?',
        'ID: ' + job_id,
        function() {
            toggle_schedule_status(job_id, STATUS_KEYS[1]);
            globalSendCommand('execute', 'id=' + job_id, null, null, null);
        }
    );

}

function delete_job(job_id) {
    confirm_modal('일정을 삭제할까요?',
        'ID: ' + job_id,
        function() {
        globalSendCommand('delete', 'id=' + job_id, null, null, function(result) {
            if (result.ret == 'success') {
                globalRequestSearch(1);
            }
        });
    });
}

function schedule_modal_by_id(from, job_id) {
    globalSendCommand("get_job", 'id=' + job_id, null, null, function(result) {
        if (result.ret == 'success') {
            schedule_modal(from, result.data);
        }
    });
}

function schedule_modal(from, data) {
    if (from == 'edit') {
        // 단일 편집
        set_form_by_task(data.task);
        E_SAVE_BTN.data('id', [data.id]);
        E_TASK.prop('value', data.task);
        E_DESC.prop('value', data.desc);
        E_PATH.prop('value', data.target);
        E_VFS.prop('value', data.vfs);
        E_RECUR.bootstrapToggle((data.recursive) ? 'on' : 'off');
        $('input[id^="sch-scan-mode"]:radio[value="' + data.scan_mode + '"]').prop('checked', true);
        disabled_by_scan_mode(data.scan_mode);
        E_SCAN_PERIODIC_ID.prop('value', data.periodic_id);
        $('input[id^="sch-schedule-mode"]:radio[value="' + data.schedule_mode + '"]').prop('checked', true);
        disabled_by_schedule_mode(data.schedule_mode);
        E_INTERVAL.prop('value', data.schedule_interval);
        E_SCH_AUTO.bootstrapToggle((data.schedule_auto_start) ? 'on' : 'off');
        E_MODAL_TITLE.html('일정 편집 - ' + data.id);
        clear_type = data.clear_type ? data.clear_type : SECTION_TYPE_KEYS[0];
        $('input[id^="sch-clear-type"]:radio[value="' + clear_type + '"]').prop('checked', true);
        set_clear_level(clear_type);
        set_plex_sections(clear_type, E_CLEAR_SECTION, SECTIONS);
        E_CLEAR_SECTION.prop('value', data.clear_section);
        E_CLEAR_LEVEL.prop('value', data.clear_level);
        E_TARGET_SECTION.prop('value', data.section_id);
    } else if (from == 'multiple-edit') {
        set_form_by_task('multiple-edit');
        E_MODAL_TITLE.html('일정 일괄 편집 - ' + data);
        E_SAVE_BTN.data('id', data);
        E_TASK.prop('value', '');
        E_DESC.prop('value', '');
        E_PATH.prop('value', '');
        E_TARGET_SECTION.prop('value', '');
        E_VFS.prop('value', '');
        E_RECUR_SEL.prop('value', '');
        E_SCAN_RADIO_0.prop('checked', false);
        E_SCAN_RADIO_1.prop('checked', false);
        E_SCAN_RADIO_2.prop('checked', false);
        E_SCAN_PERIODIC_ID.prop('value', '');
        E_SCH_RADIO_0.prop('checked', false);
        E_SCH_RADIO_1.prop('checked', false);
        E_SCH_RADIO_2.prop('checked', false);
        E_INTERVAL.prop('value', '');
        E_SCH_AUTO_SEL.prop('value', '');
        E_CLEAR_RADIO_0.prop('checked', false);
        E_CLEAR_RADIO_1.prop('checked', false);
        E_CLEAR_RADIO_2.prop('checked', false);
        E_CLEAR_LEVEL.prop('value', '');
        E_CLEAR_SECTION.prop('value', '');
    } else {
        // 새로 추가
        set_form_by_task(TASK_KEYS[0]);
        E_TASK.prop('value', TASK_KEYS[0]);
        E_SAVE_BTN.data('id', [-1]);
        E_DESC.prop('value', '');
        if (from == 'browser') {
            // 브라우저에서 추가
            E_PATH.prop('value', data.target);
        } else {
            E_PATH.prop('value', '/');
        }
        E_VFS.prop('value', VFS);
        E_RECUR.bootstrapToggle('off');
        E_SCAN_RADIO_0.prop('checked', true);
        E_SCAN_PERIODIC_ID.prop('value', 1);
        E_SCH_RADIO_0.prop('checked', true);
        E_INTERVAL.prop('value', '');
        E_SCH_AUTO.bootstrapToggle('off');
        E_CLEAR_RADIO_0.prop('checked', true);
        disabled_by_schedule_mode(FF_SCHEDULE_KEYS[0]);
        disabled_by_scan_mode(SCAN_MODE_KEYS[0]);
        set_plex_sections(E_CLEAR_RADIO_0.prop('value'), E_CLEAR_SECTION, SECTIONS);
        set_clear_level(E_CLEAR_RADIO_0.prop('value'));
        E_MODAL_TITLE.html("일정 추가");
    }
    E_MODAL.modal({backdrop: 'static', keyboard: true}, 'show');
}

function set_form_by_task(task) {
    E_GROUP_PATH.detach();
    E_GROUP_RCLONE.detach();
    E_GROUP_SCAN.detach();
    E_GROUP_CLEAR.detach();
    E_GROUP_SCH.detach();
    E_SCH_RADIO_0.prop('disabled', false);
    E_SCH_RADIO_2.prop('disabled', false);
    E_RECUR.bootstrapToggle();
    E_SCH_AUTO.bootstrapToggle();
    E_RECUR.parent().show();
    E_RECUR_SEL.hide();
    E_SCH_AUTO.parent().show();
    E_SCH_AUTO_SEL.hide();
    switch(task){
        case TASK_KEYS[0]:
            E_SCH_SETTING.append(E_GROUP_PATH);
            E_SCH_SETTING.append(E_GROUP_RCLONE);
            E_SCH_SETTING.append(E_GROUP_SCAN);
            E_SCH_SETTING.append(E_GROUP_SCH);
            break;
        case TASK_KEYS[1]:
            E_SCH_SETTING.append(E_GROUP_PATH);
            E_SCH_SETTING.append(E_GROUP_RCLONE);
            E_SCH_SETTING.append(E_GROUP_SCH);
            break;
        case TASK_KEYS[2]:
            E_SCH_SETTING.append(E_GROUP_PATH);
            E_SCH_SETTING.append(E_GROUP_SCAN);
            E_SCH_SETTING.append(E_GROUP_SCH);
            break;
        case TASK_KEYS[3]:
            E_SCH_SETTING.append(E_GROUP_RCLONE);
            E_SCH_SETTING.append(E_GROUP_SCH);
            break;
        case TASK_KEYS[4]:
            E_SCH_SETTING.append(E_GROUP_CLEAR);
            E_SCH_SETTING.append(E_GROUP_SCH);
            break;
        case TASK_KEYS[5]:
            E_SCH_SETTING.append(E_GROUP_SCH);
            if (E_SCH_AUTO.parent().is(":visible")) {
                E_SCH_RADIO_1.prop('checked', true);
            }
            disabled_by_schedule_mode(FF_SCHEDULE_KEYS[1]);
            E_SCH_RADIO_0.prop('disabled', true);
            E_SCH_RADIO_2.prop('disabled', true);
            break;
        case 'multiple-edit':
            E_SCH_SETTING.append(E_GROUP_PATH);
            E_SCH_SETTING.append(E_GROUP_RCLONE);
            E_SCH_SETTING.append(E_GROUP_SCAN);
            E_SCH_SETTING.append(E_GROUP_SCH);
            E_SCH_SETTING.append(E_GROUP_CLEAR);
            E_INTERVAL.prop('disabled', false);
            E_PATH.prop('disabled', false);
            E_PATH_BTN.prop('disabled', false);
            E_TARGET_SECTION.prop('disabled', false);
            E_SCAN_PERIODIC_ID.prop('disabled', false);
            E_RECUR.parent().hide();
            E_RECUR_SEL.show();
            E_SCH_AUTO.parent().hide();
            E_SCH_AUTO_SEL.show();
            break;
    }
}

function set_search_option2_by_option1(opt) {
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

// build_* 함수가 정의된 후 할당
const SCH_FORM_LINE = '<hr class="">'
const SCH_FORM_TASK = build_form_select('sch-task', '작업', TASK_OPTS, 9, '일정으로 등록할 작업');
const SCH_FORM_DESC = build_form_text('sch-description', '설명', '', 9, '일정 목록에 표시될 제목');
const SCH_FORM_GROUP_TASK = build_form_group('sch-form-group-task', [SCH_FORM_TASK, SCH_FORM_DESC, SCH_FORM_LINE]);
const SCH_FORM_PATH = build_form_text_btn('sch-target-path', '로컬 경로', '', 'sch-target-path-btn', '경로 탐색', 10, '새로고침/스캔 할 경로<br>Flaskfarm에서 접근 가능한 로컬 경로');
const SCH_FORM_SECTION = build_form_select('sch-target-section', '라이브러리 섹션', [{value: -1, name: '선택 안 함'}], 5, '새로고침/스캔 할 라이브러리 섹션<br>로컬 경로와 비교하여 하위인 경로가 선택됩니다.')
const SCH_FORM_GROUP_PATH = build_form_group('sch-form-group-path', [SCH_FORM_PATH, SCH_FORM_SECTION, SCH_FORM_LINE]);
const SCH_FORM_VFS = build_form_select('sch-vfs', 'VFS 리모트', VFSES, 5, 'rclone rc로 접근 가능한 리모트 이름<br>ex. gds:');
const SCH_FORM_RECURSIVE = build_form_checkbox('sch-recursive', 'recursive', [{value: true, name: 'On'}, {value: false, name: 'Off'}], 9, 'rclone vfs/refresh의 --recursive 옵션 적용 여부<br>On: 지정된 경로의 모든 하위 경로도 vfs/refresh<br>Off: 지정된 경로만 vfs/refresh');
const SCH_FORM_GROUP_RCLONE = build_form_group('sch-form-group-rclone', [SCH_FORM_VFS, SCH_FORM_RECURSIVE, SCH_FORM_LINE]);
const SCH_FORM_SCAN_TYPE = build_form_radio('sch-scan-mode', '스캔 방식', SCAN_OPTS, 9, '');
const SCH_FORM_SCAN_PERIODIC = build_form_select('sch-scan-mode-periodic-id', '주기적 스캔 작업', [], 9, 'Plexmate 플러그인의 주기적 스캔 작업 목록')
const SCH_FORM_GROUP_SCAN = build_form_group('sch-form-group-scan', [SCH_FORM_SCAN_TYPE, SCH_FORM_SCAN_PERIODIC, SCH_FORM_LINE]);
const SCH_FORM_CLEAR_TYPE = build_form_radio('sch-clear-type', '파일 정리 유형', CLEAR_OPTS, 9, '파일 정리할 라이브러리의 유형')
const SCH_FORM_CLEAR_LEVEL = build_form_select('sch-clear-level', '파일 정리 단계', [], 3, 'Plexmate 파일 정리 단계')
const SCH_FORM_CLEAR_SECTION = build_form_select('sch-clear-section', '파일 정리 섹션', [], 5, '파일 정리할 라이브러리 섹션')
const SCH_FORM_GROUP_CLEAR = build_form_group('sch-form-group-clear', [SCH_FORM_CLEAR_TYPE, SCH_FORM_CLEAR_LEVEL, SCH_FORM_CLEAR_SECTION, SCH_FORM_LINE]);
const SCH_FORM_SCH_MODE = build_form_radio('sch-schedule-mode', '일정 방식', SCHEDULE_OPTS, 9, '')
const SCH_FORM_SCH_INTERVAL = build_form_text('sch-schedule-interval', '시간 간격', '', 5, 'Interval(minute 단위) 혹은 Cron 설정');
const SCH_FORM_SCH_AUTO = build_form_checkbox('sch-schedule-auto-start', '시작시 일정 등록', [{value: true, name: 'On'}, {value: false, name: 'Off'}], 9, '');
const SCH_FORM_GROUP_SCH = build_form_group('sch-form-group-sch', [SCH_FORM_SCH_MODE, SCH_FORM_SCH_INTERVAL, SCH_FORM_SCH_AUTO, SCH_FORM_LINE]);

const E_SCH_SETTING = $('#sch-setting');
E_SCH_SETTING.append(SCH_FORM_GROUP_TASK);
E_SCH_SETTING.append(SCH_FORM_GROUP_PATH);
E_SCH_SETTING.append(SCH_FORM_GROUP_RCLONE);
E_SCH_SETTING.append(SCH_FORM_GROUP_SCAN);
E_SCH_SETTING.append(SCH_FORM_GROUP_CLEAR);
E_SCH_SETTING.append(SCH_FORM_GROUP_SCH);
// E_SCH_SETTING 에 element가 구현된 후 selector 사용
const E_TASK = $('#sch-task');
const E_DESC = $('#sch-description');
const E_GROUP_TASK = $('#sch-form-group-task');
const E_PATH = $('#sch-target-path');
const E_PATH_BTN = $('#sch-target-path-btn');
const E_TARGET_SECTION = $('#sch-target-section');
const E_GROUP_PATH = $('#sch-form-group-path');
const E_VFS = $('#sch-vfs');
const E_RECUR = $('#sch-recursive');
const E_RECUR_SEL = $('#sch-recursive-select');
const E_GROUP_RCLONE = $('#sch-form-group-rclone');
const E_SCAN_RADIO_0 = $('#sch-scan-mode0');
const E_SCAN_RADIO_1 = $('#sch-scan-mode1');
const E_SCAN_RADIO_2 = $('#sch-scan-mode2');
const E_SCAN_PERIODIC_ID = $('#sch-scan-mode-periodic-id');
const E_GROUP_SCAN = $('#sch-form-group-scan');
const E_CLEAR_SECTION = $('#sch-clear-section');
const E_CLEAR_RADIO_0 = $('#sch-clear-type0');
const E_CLEAR_RADIO_1 = $('#sch-clear-type1');
const E_CLEAR_RADIO_2 = $('#sch-clear-type2');
const E_CLEAR_LEVEL = $('#sch-clear-level');
const E_GROUP_CLEAR = $('#sch-form-group-clear');
const E_SCH_RADIO_0 = $('#sch-schedule-mode0');
const E_SCH_RADIO_1 = $('#sch-schedule-mode1');
const E_SCH_RADIO_2 = $('#sch-schedule-mode2');
const E_SCH_AUTO = $('#sch-schedule-auto-start');
const E_SCH_AUTO_SEL = $('#sch-schedule-auto-start-select');
const E_INTERVAL = $('#sch-schedule-interval');
const E_GROUP_SCH = $('#sch-form-group-sch');
const E_SAVE_BTN = $('#sch-save-btn');
const E_ADD_BTN = $('#sch-add-btn');
const E_MODAL_TITLE = $('#sch-add-modal_title');
const E_MODAL = $('#sch-add-modal')
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
const SOCKET = io.connect(window.location.href)
const E_MULTIPLE_DEL = $('#multiple-del');
const E_MULTIPLE_EDIT = $('#multiple-edit');
const E_SCH_LIST_TBODY = $('#sch-list-table tbody');

// 일정 업무 선택에 따라 inputs (비)활성화
E_TASK.on('change', function(e) {
    set_form_by_task($(this).prop('value'));
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
E_RECUR.on('change', function(e){
    E_RECUR_SEL.prop('value', $(this).prop('checked'));
});
// 스캔 방식에 따라 inputs (비)활성화
$('input[id^="sch-scan-mode"]:radio').change(function() {
    disabled_by_scan_mode($(this).prop('value'));
});
// 라이브러리 타입에 따라 목록 변경
$('input[id^="sch-clear-type"]:radio').change(function() {
    set_plex_sections($(this).prop('value'), E_CLEAR_SECTION, SECTIONS);
    set_clear_level($(this).prop('value'));
})
// 일정 방식 선택에 따라 inputs (비)활성화
$('input[id^="sch-schedule-mode"]:radio').change(function() {
    E_SCH_AUTO.bootstrapToggle('off');
    disabled_by_schedule_mode($(this).prop('value'));
});
E_SCH_AUTO.on('change', function(e){
    E_SCH_AUTO_SEL.prop('value', $(this).prop('checked'));
});
// 일정 저장 버튼
E_SAVE_BTN.on('click', function() {
    let ids = $(this).data('id');
    let formdata = getFormdata('#sch-setting'); // getFormdata()@ff_common1.js
    for (let i in ids) {
        formdata += '&id=' + ids[i];
    }
    globalSendCommand('save', formdata, null, null, function(result) {
        if (result.ret == 'success') {
            E_MODAL.modal('hide');
            globalRequestSearch(1);
        }
    });
});
// 일정 추가 버튼
E_ADD_BTN.on('click', function(e) {
    e.preventDefault();
    schedule_modal('new', '');
});
E_MODAL.on('shown.bs.modal', function (e) {
});
E_MODAL.on('hidden.bs.modal', function (e) {
    E_TASK.on('change', function(e) {
        set_form_by_task($(this).prop('value'));
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
    browser_command({command: 'list', path: dir, vfs: VFS, recursive: false, scan_mode: SCAN_MODE_KEYS[0]});
});
PERIODICS.forEach(function(item, index) {
    E_SCAN_PERIODIC_ID.append(
        $('<option></option>').prop('value', item.idx).html(item.idx + '. ' + item.name + ' : ' + item.desc)
    );
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
    set_search_option2_by_option1($(this).prop('value'));
});
// 초기 리스트 불러오기
// f'{order}|{page}|{page_size}|{keyword}|{option1}|{option2}'
E_GLOBAL_SEARCH_ORDER.prop('value', LAST_LIST_OPTIONS[0]);
E_GLOBAL_SEARCH_LENGTH.prop('value', LAST_LIST_OPTIONS[2]);
E_GLOBAL_SEARCH_KEYWORD.prop('value', LAST_LIST_OPTIONS[3]);
E_GLOBAL_SEARCH_OPTION1.prop('value', LAST_LIST_OPTIONS[4]);
set_search_option2_by_option1(E_GLOBAL_SEARCH_OPTION1.prop('value'));
E_GLOBAL_SEARCH_OPTION2.prop('value', LAST_LIST_OPTIONS[5]);
globalRequestSearch(1);
// search reset button
E_SEARCH_RESET_BTN.on('click', function(e) {
    E_GLOBAL_SEARCH_LENGTH.prop('value', 10);
    E_GLOBAL_SEARCH_ORDER.prop('value', 'desc');
    E_GLOBAL_SEARCH_OPTION1.prop('value', SEARCH_KEYS[0]);
    set_search_option2_by_option1(E_GLOBAL_SEARCH_OPTION1.prop('value'));
    E_GLOBAL_SEARCH_OPTION2.prop('value', 'all');
    E_GLOBAL_SEARCH_KEYWORD.prop('value', '');
    globalRequestSearch(1, false);
});
// 초기 디렉토리 불러오기
browser_command({
    command: 'list',
    path: E_BROWSER_WD.prop('value'),
    recursive: false,
    vfs: VFS,
    scan_mode: SCAN_MODE_KEYS[0],
});
SOCKET.on('result', function(result) {
    if (result) {
        if (result.data.msg) {
            notify(result.data.msg, 'info');
        }
        toggle_schedule_status(result.data.id, result.data.status);
    }
});
E_MULTIPLE_DEL.on('click', function(e) {
    let selected = $('input[class="selectable"]:checked').map((i, el) => el.value).get();
    if (selected.length > 0) {
        confirm_modal(
            '선택한 항목을 삭제할까요?',
            selected.length + ' 개의 항목이 모두 삭제됩니다.',
            function() {
                let query = '';
                for (let i in selected) {
                    query += 'id=' + selected[i] + '&';
                }
                globalSendCommand('delete', query, null, null, function(result) {
                    if (result.ret == 'success') {
                        globalRequestSearch(1);
                    }
                    E_SELECT_ALL.prop('checked', false);
                });
            }
        );
    } else {
        notify('선택된 항목이 없습니다.', 'warning');
    }
});
E_MULTIPLE_EDIT.on('click', function(e) {
    let selected = $('input[class="selectable"]:checked').map((i, el) => el.value).get();
    if (selected.length > 0) {
        E_TASK.off('change');
        schedule_modal('multiple-edit', selected);
    } else {
        notify('선택된 항목이 없습니다.', 'warning');
    }
});
