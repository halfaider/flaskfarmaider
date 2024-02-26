E_TRASH_TOTAL_DELETED = $('#trash-total-deleted');
E_TRASH_TOTAL_PATHS = $('#trash-total-paths');
E_TRASH_SECTIONS = $('#trash-sections');
E_TRASH_SECTION_TYPE = $('#trash-section-type');
E_TRASH_BTN_LIST = $('#trash-btn-list');
E_TRASH_BTN_STOP = $('#trash-btn-stop');
E_TRASH_TASK = $('#trash-task');
E_TRASH_VFS = $('#trash-vfs');
E_TRASH_BTN_EXCEUTE = $('#trash-btn-execute');

function get_list(page_no) {
    let lib_type = E_TRASH_SECTION_TYPE.prop('value');
    let lib_id = E_TRASH_SECTIONS.prop('value');
    let query = 'section_type=' + lib_type + '&section_id=' + lib_id + '&page=' + page_no + '&limit=50'
    globalSendCommandPage('list', query, null, null, function(result) {
        make_list(result.data);
    });
}

function make_list(data) {
    let tbody = $('#trash-list tbody')
    tbody.empty();
    E_TRASH_TOTAL_DELETED.text(data.total);
    E_TRASH_TOTAL_PATHS.text(data.total_paths);
    if (data.data) {
        data.data.forEach(function(item) {
            let col_id = '<td class="text-center">' + item.id + '</td>';
            let col_deleted = '<td class="text-center">' + item.deleted_at + '</td>';
            let col_file = '<td class="">' + item.file + '</td>';
            let col_manage = '<td class="text-center">';
            col_manage += '<a href="#refresh-scan" class="trash-list-command mr-2 text-info" data-command="refresh_scan" title="새로고침 후 스캔"><i class="fa fa-lg fa-spinner" aria-hidden="true"></i></a>';
            col_manage += '<a href="#refresh" class="trash-list-command mr-2" data-command="refresh" title="새로고침"><i class="fa fa-lg fa-refresh" aria-hidden="true"></i></a>';
            col_manage += '<a href="#scan" class="trash-list-command mr-2" data-command="scan" title="스캔"><i class="fa fa-lg fa-search" aria-hidden="true"></i></a>';
            col_manage += '<a href="#delete" class="trash-list-delete text-warning" title="삭제"><i class="fa fa-lg fa-trash" aria-hidden="true"></i></a>';
            col_manage += '</td>';
            let row = '<tr class="" data-id="' + item.id + '" data-metadata="' + item.metadata_item_id + '" data-path="' + item.file + '">' + col_id + col_deleted + col_file + col_manage + '</tr>';
            tbody.append(row);
        });
    }
    // 페이지
    pagination($('nav.trash-pagination'), data.page, data.total, data.limit, get_list);

    // 관리 메뉴
    $('.trash-list-command').on('click', function(e) {
        let command = $(this).data('command');
        let path = $(this).closest('tr').data('path');
        // trash 목록은 파일 경로를 보여주고 있으나 새로고침/스캔 시에는 폴더 경로로 요청해야 함.
        path = path.replace(path.replace(/^.*[\\\/]/, ''), '');
        let query = 'target=' + path;
        query += '&vfs=' + E_TRASH_VFS.prop('value');
        query += '&recursive=false';
        query += '&scan_mode=' + SCAN_MODE_KEYS[2];
        query += '&periodic_id=-1';
        confirm_modal(TASKS[command].name + '을(를) 실행할까요?', path, function() {
            globalSendCommand(command, query, null, null, null);
        });
    });
    $('.trash-list-delete').on('click', function(e) {
        let path = $(this).closest('tr').data('path');
        let metadata = $(this).closest('tr').data('metadata');
        let id = $(this).closest('tr').data('id');
        confirm_modal('이 파일을 플렉스에서 삭제할까요?', path, function() {
            globalSendCommandPage('delete', 'metadata_id=' + metadata + '&mediaitem_id=' + id, null, null, function(result) {
                if (result.ret == 'success') {
                    let page = $('ul.pagination li.active[aria-current=page]').first().text()
                    get_list(page ? page : 1);
                }
            });
        });
    });
}

E_TRASH_SECTIONS.change(function() {
    get_list(1);
});
E_TRASH_SECTION_TYPE.change(function() {
    set_plex_sections($(this).prop('value'), E_TRASH_SECTIONS, SECTIONS);
});
E_TRASH_BTN_LIST.on('click', function(e) {
    get_list(1);
});
E_TRASH_BTN_STOP.on('click', function(e) {
    globalSendCommandPage('stop', '', '', '', null);
});
E_TRASH_BTN_EXCEUTE.on('click', function(e) {
    query = 'section_id=' + E_TRASH_SECTIONS.prop('value') + '&vfs=' +E_TRASH_VFS.prop('value')
    globalSendCommandPage(E_TRASH_TASK.prop('value'), query, null, null, null);
});
// 초기 리스트
if (!LAST_LIST_OPTIONS[0]) {
    LAST_LIST_OPTIONS[0] = 'movie'
}
E_TRASH_SECTION_TYPE.prop('value', LAST_LIST_OPTIONS[0]);
set_plex_sections(LAST_LIST_OPTIONS[0], E_TRASH_SECTIONS, SECTIONS);
if (LAST_LIST_OPTIONS[1]) {
    E_TRASH_SECTIONS.prop('value', LAST_LIST_OPTIONS[1]);
}
if (LAST_LIST_OPTIONS[0] && LAST_LIST_OPTIONS[1]) {
    get_list(1);
}
