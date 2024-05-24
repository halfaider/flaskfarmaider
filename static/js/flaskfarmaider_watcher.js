const OBSERVER_OPTS = [
    { value: 'inotify', name: 'inotify' },
    { value: 'windows', name: 'Windows' },
    { value: 'polling', name: 'Polling' },
];

const HANDLERS_OPTS = [
    { value: 'plex_mate', name: 'plex_mate 스캔 요청' },
    { value: 'discord', name: '디스코드 알람 전송' },
]

const EVENTS_OPTS = [
    { value: 'created', name: '생성' },
    { value: 'deleted', name: '삭제' },
    { value: 'modified', name: '수정' },
    { value: 'moved', name: '이동' },
]

function make_list(data) {
    $('#select-all').prop('checked', false);
    $('#list-table tbody').empty();
    for (let model of data){
        let col_checkbox = '<td class="text-center"><input type="checkbox" class="selectable" value="' + model.id + '"></td>';
        let col_id = '<td class="text-center">' + model.id + '</td>';
        let col_observer = '<td class="text-center">' + model.observer + '</td>';
        let col_path = '<td class="">' + model.path + '</td>';
        let col_enable = '<td class="text-center"><input id="watch-enable-' + model.id;
        col_enable += '" type="checkbox" ' + ((model.enable) ? 'checked' : '');
        col_enable += ' data-toggle="toggle" class="watch-enable" /></td>';
        let col_manage = '<td class="text-center">';
        col_manage += '<a href="#edit" class="list-edit" title="편집"><i class="fa fa-lg fa-pencil-square-o" aria-hidden="true"></i></a>';
        col_manage += '<a href="#delete" class="list-delete mx-2 text-warning" title="삭제"><i class="fa fa-lg fa-trash" aria-hidden="true"></i></a>';
        col_manage += '</td>';

        let row_group = '<tr id="list-' + model.id + '" class="" data-id="'+ model.id +'">';
        row_group += col_checkbox + col_id + col_observer + col_path + col_enable + col_manage + '</tr>';
        $('#list-table tbody').append(row_group);
    }
    // 토글 활성화
    $('.watch-enable').bootstrapToggle();
    $('.watch-enable').on('change', function(e) {
        let _id = $(this).closest('tr').data('id');
        let checked = $(this).prop('checked');
        globalSendCommand('save', 'id=' + _id + '&watch-enable=' + checked, null, null, null);
    });
    $('.watch-enable ~ div.toggle-group').on('click', function(e) {
        // collapse까지 bubble up 되는 것 방지
        e.stopPropagation();
        $(this).prev().bootstrapToggle('toggle');
    });
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

function reset_form() {
    $('#save-btn').data('id', null);
    $('#watch-observer').prop('value', null);
    $('#watch-path').prop('value', null);
    $('#watch-patterns').prop('value', null);
    $('#watch-ignore-patterns').prop('value', null);
    $('#watch-events-created').prop('checked', false);
    $('#watch-events-deleted').prop('checked', false);
    $('#watch-events-modified').prop('checked', false);
    $('#watch-events-moved').prop('checked', false);
    $('#watch-handlers-plex_mate').prop('checked', false);
    $('#watch-handlers-discord').prop('checked', false);
    $('#watch-ignore-directory').bootstrapToggle('off');
    $('#watch-case-sensitive').bootstrapToggle('off');
    $('#watch-enable').bootstrapToggle('off');
    $('#watch-timeout').prop('value', null);
}

function open_modal(from, data) {
    reset_form();
    if (from == 'edit') {
        console.log(data);
        $('#add-modal_title').html('감시 수정');
        $('#save-btn').data('id', [data.id]);
        $('#watch-observer').prop('value', data.observer);
        $('#watch-path').prop('value', data.path);
        $('#watch-patterns').prop('value', data.patterns);
        $('#watch-ignore-patterns').prop('value', data.ignore_patterns);
        events = (data.events || '').split('|');
        for (idx in events) {
            $('#watch-events-' + events[idx]).prop('checked', true);
        }
        handlers = (data.handlers || '').split('|');
        for (idx in handlers) {
            $('#watch-handlers-' + handlers[idx]).prop('checked', true);
        }
        $('#watch-ignore-directory').bootstrapToggle((data.ignore_directory) ? 'on' : 'off');
        $('#watch-case-sensitive').bootstrapToggle((data.case_sensitive) ? 'on' : 'off');
        $('#watch-enable').bootstrapToggle((data.enable) ? 'on' : 'off');
        $('#watch-timeout').prop('value', data.timeout);
    } else {
        $('#add-modal_title').html('감시 추가');
        $('#save-btn').data('id', [-1]);
    }
    $('#add-modal').modal({backdrop: 'static', keyboard: true}, 'show');
}

const FORM_LINE = '<hr class="">'
const FORM_OBSERVER = build_form_select('watch-observer', '감시자', OBSERVER_OPTS, 3, 'inotify: 리눅스<br/>Windows: 윈도우<br/>Polling: 모든 플랫폼');
const FORM_GROUP_OBSERVER = build_form_group('watch-form-group-observer', [FORM_OBSERVER, FORM_LINE]);
$('#setting').append(FORM_GROUP_OBSERVER);
const FORM_PATH = build_form_text('watch-path', '감시 경로', '', 10, '감시 경로');
const FORM_PATTERNS = build_form_textarea('watch-patterns', '일치 패턴', '', 10, 5, '패턴과 일치하는 경로만 포함')
const FORM_IGNORE_PATTERNS = build_form_textarea('watch-ignore-patterns', '제외 패턴', '', 10, 5, '패턴과 일치하는 경로 제외')
const FORM_GROUP_PATH = build_form_group('watch-form-group-path', [FORM_PATH, FORM_PATTERNS, FORM_IGNORE_PATTERNS, FORM_LINE]);
$('#setting').append(FORM_GROUP_PATH);
const FORM_EVENTS = build_form_checkbox_multi('watch-events', '이벤트', EVENTS_OPTS, 5, '처리할 이벤트<br>중복 선택')
const FORM_HANDLERS = build_form_checkbox_multi('watch-handlers', '작업', HANDLERS_OPTS, 5, '이벤트를 처리할 대상<br>중복 선택')
const FORM_GROUP_HANDLERS = build_form_group('watch-form-group-handlers', [FORM_EVENTS, FORM_HANDLERS, FORM_LINE]);
$('#setting').append(FORM_GROUP_HANDLERS);
const FORM_IGNORE_DIRECTORY = build_form_checkbox2('watch-ignore-directory', '디렉토리 포함', [{value: true, name: 'On'}, {value: false, name: 'Off'}], 9, '감시 대상에 디렉토리 포함 여부');
const FORM_CASE_SENSITIVE = build_form_checkbox2('watch-case-sensitive', '대소문자 구분', [{value: true, name: 'On'}, {value: false, name: 'Off'}], 9, '경로 문자의 대소문자 구분 여부');
const FORM_TIMEOUT = build_form_input('watch-timeout', '타임아웃/Polling 간격', '', 3, '초 단위', true);
const FORM_ENABLE = build_form_checkbox2('watch-enable', '활성화', [{value: true, name: 'On'}, {value: false, name: 'Off'}], 9, '');
const FORM_GROUP_ETC = build_form_group('watch-form-group-etc', [FORM_IGNORE_DIRECTORY, FORM_CASE_SENSITIVE, FORM_TIMEOUT, FORM_ENABLE]);
$('#setting').append(FORM_GROUP_ETC);

$('#watch-ignore-directory').bootstrapToggle();
$('#watch-case-sensitive').bootstrapToggle();
$('#watch-enable').bootstrapToggle();

// 초기 리스트 불러오기
globalRequestSearch(1);



