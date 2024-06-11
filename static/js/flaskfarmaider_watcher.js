const OBSERVER_OPTS = [
    { value: 'auto', name: 'Auto' },
    { value: 'inotify', name: 'inotify' },
    { value: 'windows', name: 'Windows' },
    { value: 'polling', name: 'Polling' },
];

const CONDUIT_OPTS = [
    { value: 'rclone', name: 'Rclone vfs/refresh 요청' },
    { value: 'plex', name: 'Plex Web API 스캔 요청' },
    { value: 'plex_mate', name: 'plex_mate 스캔 요청' },
    { value: 'shell_command', name: 'Shell 명령어 실행' },
    { value: 'discord', name: 'Discord Webhook 전송' },
]

const EVENTS_OPTS = [
    { value: 'created', name: '생성' },
    { value: 'deleted', name: '삭제' },
    { value: 'moved', name: '이동' },
    { value: 'modified', name: '수정' },
    { value: 'opened', name: '열림' },
    { value: 'closed', name: '닫힘' },
]

function make_list(data) {
    $('#select-all').prop('checked', false);
    $('#list-table tbody').empty();
    for (let model of data){
        let col_checkbox = '<td class="text-center"><input type="checkbox" class="selectable" value="' + model.id + '"></td>';
        let col_id = '<td class="text-center">' + model.id + '</td>';
        let col_observer = '<td class="text-center">' + model.observer + '</td>';
        let col_paths = '<td class="">' + join_by(model.paths, '<br>') + '</td>';
        let col_enable = '<td class="text-center"><div class="custom-control custom-switch"><input id="watch-enable-' + model.id;
        col_enable += '" type="checkbox" ' + ((model.enable) ? 'checked' : '');
        col_enable += ' class="custom-control-input watch-enable" ><label class="custom-control-label" for="watch-enable-' + model.id + '"></label></div></td>';
        let col_manage = '<td class="text-center">';
        col_manage += '<a href="#edit" class="list-edit" title="편집"><i class="fa fa-lg fa-pencil-square-o" aria-hidden="true"></i></a>';
        col_manage += '<a href="#delete" class="list-delete mx-2 text-warning" title="삭제"><i class="fa fa-lg fa-trash" aria-hidden="true"></i></a>';
        col_manage += '</td>';

        let row_group = '<tr id="list-' + model.id + '" class="" data-id="'+ model.id +'">';
        row_group += col_checkbox + col_id + col_observer + col_paths + col_enable + col_manage + '</tr>';
        $('#list-table tbody').append(row_group);
    }
    // 토글 활성화
    //$('.watch-enable').bootstrapToggle();
    $('.watch-enable').on('change', function(e) {
        let _id = $(this).closest('tr').data('id');
        let checked = $(this).prop('checked');
        globalSendCommand('save', 'id=' + _id + '&watch-enable=' + checked, null, null, null);
    });
    //$('.watch-enable ~ div.toggle-group').on('click', function(e) {
    //    // collapse까지 bubble up 되는 것 방지
    //    e.stopPropagation();
    //    $(this).prev().bootstrapToggle('toggle');
    //});
    // 관리 메뉴
    $('.list-edit').on('click', function(e) {
        console.log('list-edit');
        open_modal_by_id('edit', $(this).closest('tr').data('id'));
    });
    $('.list-delete').on('click', function(e) {
        console.log('list-delete');
        delete_model($(this).closest('tr').data('id'));
    });
}

function parse_events(_events) {
    let result = {
        created: false,
        deleted: false,
        moved: false,
        modified: false,
        opened: false,
        closed: false
    };
    let events = JSON.parse(_events);
    console.log(events);
    if (events !== null) {
        for (_event of events) {
            result[_event] = true;
        }
    }
    return result;
}

function parse_conduits(_conduits) {
    let conduits = JSON.parse(_conduits);
    if (conduits !== null) {
        return conduits;
    } else {
        return {};
    }
}

function reset_form() {
    $('#save-btn').data('id', [-1]);
    $('#watch-observer option:first').prop('selected', true);
    $('#watch-timeout').prop('value', 60);
    $('#watch-ignore-directory').prop('checked', false);
    $('#watch-case-sensitive').prop('checked', true);
    $('#watch-recursive').prop('checked', false);
    $('#watch-enable').prop('checked', false);
    $('#watch-paths').prop('value', null);
    $('#watch-events-created').prop('checked', true);
    $('#watch-events-deleted').prop('checked', false);
    $('#watch-events-modified').prop('checked', false);
    $('#watch-events-moved').prop('checked', false);
    $('#watch-events-opened').prop('checked', false);
    $('#watch-events-closed').prop('checked', false);
    $('#watch-events-interval').prop('value', 2);
    $('#watch-patterns').prop('value', null);
    $('#watch-ignore-patterns').prop('value', null);
    $('#watch-mappings').prop('value', null);
    $('#watch-conduits-shell').prop('checked', false);
    $('#watch-conduits-shell-priority').prop('value', 30);
    $('#watch-conduits-shell-mappings').prop('value', null);
    $('#watch-conduits-shell-command').prop('value', null);
    $('#watch-conduits-rclone').prop('checked', false);
    $('#watch-conduits-rclone-priority').prop('value', 50);
    $('#watch-conduits-rclone-mappings').prop('value', null);
    if (VFS !== null && VFS !== '') {
        $('#watch-conduits-rclone-vfs option[value="' + VFS + '"]').prop('selected', true);
    } else {
        $('#watch-conduits-rclone-vfs option:first').prop('selected', true);
    }
    $('#watch-conduits-plex_mate').prop('checked', false);
    $('#watch-conduits-plex_mate-priority').prop('value', 50);
    $('#watch-conduits-plex_mate-mappings').prop('value', null);
    $('#watch-conduits-plex').prop('checked', false);
    $('#watch-conduits-plex-priority').prop('value', 50);
    $('#watch-conduits-plex-mappings').prop('value', null);
}

function open_modal(from, data) {
    reset_form();
    if (from == 'edit') {
        console.log(data);
        $('#add-modal_title').html('감시 수정');
        $('#save-btn').data('id', [data.id]);
        $('#watch-observer').prop('value', data.observer);
        $('#watch-timeout').prop('value', data.timeout);
        $('#watch-ignore-directory').prop('checked', data.ignore_directory);
        $('#watch-case-sensitive').prop('checked', data.case_sensitive);
        $('#watch-recursive').prop('checked', data.recursive);
        $('#watch-enable').prop('checked', data.enable);
        $('#watch-paths').prop('value', join_by(data.paths));
        let events = parse_events(data.events);
        for (const key in events) {
            $('#watch-events-' + key).prop('checked', events[key]);
        }
        $('#watch-events-interval').prop('value', data.events_interval);
        $('#watch-patterns').prop('value', join_by(data.patterns));
        $('#watch-ignore-patterns').prop('value', join_by(data.ignore_patterns));
        $('#watch-mappings').prop('value', join_by(data.mappings));
        let conduits = parse_conduits(data.conduits);
        console.log(conduits);
        for (const key in conduits) {
            $('#watch-conduits-' + key).prop('checked', true);
            $('#watch-conduits-' + key + '-priority').prop('value', conduits[key].priority);
            if (conduits[key].mappings) {
                $('#watch-conduits-' + key + '-mappings').prop('value', conduits[key].mappings.join('\r\n'));
            }
            switch(key) {
                case 'shell':
                    if (conduits[key].command) {
                        $('#watch-conduits-' + key + '-command').prop('value', conduits[key].command);
                    }
                    break;
                case 'rclone':
                    if (conduits[key].vfs) {
                        $('#watch-conduits-' + key + '-vfs').prop('value', conduits[key].vfs);
                    }
                    break;
            }
        }
    } else {
        $('#add-modal_title').html('감시 추가');
        $('#save-btn').data('id', [-1]);
    }
    $('#add-modal').modal({backdrop: 'static', keyboard: true}, 'show');
}

// 초기 리스트 불러오기
globalRequestSearch(1);



