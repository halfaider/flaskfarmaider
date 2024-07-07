/*
After ducument ready...

FF의 confirm 모달은 플러그인의 콘텐츠보다 늦게 출력되기 때문에 documnet ready 후에 셀렉터 사용
*/
const E_CONFIRM_TITLE = $('#confirm_title');
const E_CONFIRM_BODY = $('#confirm_body');
const E_CONFIRM_BTN = $('#confirm_button');
const E_CONFIRM_MODAL = $("#confirm_modal");
const E_SELECT_ALL = $('#select-all');
const E_MULTIPLE_DEL = $('#multiple-del');
const E_MULTIPLE_EDIT = $('#multiple-edit');
const SOCKET = io.connect(window.location.href);

// 추가 버튼
$('#add-btn').on('click', function(e) {
    e.preventDefault();
    openModal('new', '');
});

// 저장 버튼
$('#save-btn').on('click', function() {
    let ids = $(this).data('id');
    let formdata = new FormData(document.getElementById('setting'));
    $('input[id$="-helper"][type="hidden"]').each(function(index) {
        let targetId = $(this).prop('id').replace('-helper', '');
        let isTargetChecked = $('#' + targetId).prop('checked');
        let isChecked = $(this).prop('checked');
        if (isChecked && !isTargetChecked) {
            formdata.append(targetId, 'off');
        }
    });
    for (let i in ids) {
        formdata.append('id', ids[i]);
    }
    let query = new URLSearchParams(formdata).toString();
    console.log(query);
    globalSendCommand('save', query, null, null, function(result) {
        if (result.ret == 'success') {
            $('#add-modal').modal('hide');
            //globalRequestSearch(1);
        }
    });
});

E_SELECT_ALL.on('click', function(e) {
    if (this.checked) {
        $('input[class="selectable"]').each(function() {
            this.checked = true;
        });
    } else {
        $('input[class="selectable"]').each(function() {
            this.checked = false;
        });
    }
});

E_MULTIPLE_DEL.on('click', function(e) {
    let selected = $('input[class="selectable"]:checked').map((i, el) => el.value).get();
    if (selected.length > 0) {
        confirmModal(
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
        openModal('multiple-edit', selected);
    } else {
        notify('선택된 항목이 없습니다.', 'warning');
    }
});

$('input:checkbox').on('change', function() {
    let helperId = $(this).prop('id') + '-helper';
    let helper = $('#' + helperId);
    if (helper) {
        helper.prop('checked', true);
    }
});