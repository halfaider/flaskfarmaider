function trash_get_list(page_no) {
    lib_id = E_TRASH_SECTIONS.prop('value');
    globalSendCommandPage('list', lib_id, page_no, 50, function(result) {
        trash_make_list(result.data);
    });
}

function trash_make_list(data) {
    tbody = $('#trash-list tbody')
    tbody.empty();
    E_TRASH_TOTAL_DELETED.text(data.total);
    E_TRASH_TOTAL_PATHS.text(data.total_paths);
    if (data.data) {
        data.data.forEach(function(item) {
            col_id = '<td class="text-center">' + item.id + '</td>';
            col_deleted = '<td class="text-center">' + item.deleted_at + '</td>';
            col_file = '<td class="">' + item.file + '</td>';
            col_menu = '<td class="text-center"><button type="button" class="btn btn-outline-primary trash-context-menu"';
            col_menu += ' data-id="' + item.id + '" data-metadata_item_id="' + item.metadata_item_id +'" data-path="' + item.file +'">메뉴</button></td>';
            row = '<tr class="">' + col_id + col_deleted + col_file + col_menu + '</tr>';
            tbody.append(row);
        });
    }
    // 페이지
    pagination($('nav.trash-pagination'), data.page, data.total, data.limit, trash_get_list);
    // 컨텍스트 메뉴
    $.contextMenu({
        selector: '.trash-context-menu',
        trigger: 'left',
        callback: function(command, opt) {
            path = opt.$trigger.data('path');
            // trash 목록에는 파일만 나오므로 요청시 모두 폴더로 요청
            path = path.replace(path.replace(/^.*[\\\/]/, ''), '');
            recursive = opt.inputs['recursive'].$input.prop('checked');
            scan_mode = opt.inputs['scan_mode'].$input.prop('value');
            globalSendCommandPage(command, path, recursive, scan_mode + "|-1", null);
        },
        items: {
            [TASK_KEYS[0]]: {
                name: TASKS[TASK_KEYS[0]].name,
                icon: 'fa-refresh',
            },
            [TASK_KEYS[1]]: {
                name: TASKS[TASK_KEYS[1]].name,
                icon: 'fa-refresh',
            },
            [TASK_KEYS[2]]: {
                name: TASKS[TASK_KEYS[2]].name,
                icon: 'fa-search',
            },
            sep2: "---------",
            delete: {
                name: '삭제',
                icon: 'fa-trash',
                callback: function(command, opt) {
                    data = opt.$trigger.data();
                    confirm_modal('이 파일을 플렉스에서 삭제할까요?', data.path, function() {
                        globalSendCommandPage(command, data.metadata_item_id, data.id, '', function(result) {
                            if (result.ret == 'success') {
                                page = $('ul.pagination li.active[aria-current=page]').first().text()
                                trash_get_list(page ? page : 1);
                            }
                        });
                    });
                },
            },
            sep3: "---------",
            recursive: {
                name: 'Recursive',
                type: 'checkbox',
                selected: false,
                disabled: true,
            },
            scan_mode: {
                name: '스캔 방식',
                type: 'select',
                options: {
                    [SCAN_MODE_KEYS[2]]: SCAN_MODES[SCAN_MODE_KEYS[2]].name,
                    [SCAN_MODE_KEYS[0]]: SCAN_MODES[SCAN_MODE_KEYS[0]].name,
                },
                selected: SCAN_MODE_KEYS[2],
                disabled: true,
            },
        },
    });
}

E_TRASH_TOTAL_DELETED = $('#trash-total-deleted');
E_TRASH_TOTAL_PATHS = $('#trash-total-paths');
E_TRASH_SECTIONS = $('#trash-sections');
E_TRASH_SECTIONS.change(function() {
    trash_get_list(1);
});
E_TRASH_SECTION_TYPE = $('#trash-section-type');
E_TRASH_SECTION_TYPE.change(function() {
    set_plex_sections($(this).prop('value'), E_TRASH_SECTIONS);
});
set_plex_sections(E_TRASH_SECTION_TYPE.prop('value'), E_TRASH_SECTIONS);
E_TRASH_BTN_LIST = $('#trash-btn-list');
E_TRASH_BTN_LIST.on('click', function(e) {
    trash_get_list(1);
});
E_TRASH_BTN_STOP = $('#trash-btn-stop');
E_TRASH_BTN_STOP.on('click', function(e) {
    globalSendCommandPage('stop', '', '', '', null);
});
E_TRASH_TASK = $('#trash-task');
E_TRASH_VFS = $('#trash-vfs');
E_TRASH_BTN_EXCEUTE = $('#trash-btn-execute');
E_TRASH_BTN_EXCEUTE.on('click', function(e) {
    globalSendCommandPage(E_TRASH_TASK.prop('value'), E_TRASH_SECTIONS.prop('value'), E_TRASH_VFS.prop('value'), '', null);
});