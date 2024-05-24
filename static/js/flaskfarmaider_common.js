// FF의 confirm 모달은 플러그인의 콘텐츠보다 늦게 출력되기 때문에 documnet ready 후에 셀렉터 사용
const E_CONFIRM_TITLE = $('#confirm_title');
const E_CONFIRM_BODY = $('#confirm_body');
const E_CONFIRM_BTN = $('#confirm_button');
const E_CONFIRM_MODAL = $("#confirm_modal");

function confirm_modal(title, content, func) {
    E_CONFIRM_TITLE.html(title);
    E_CONFIRM_BODY.html(content);
    // 클릭 이벤트가 bubble up 되면서 중복 실행됨 e.stopImmediatePropagation(); 로 해결 안 됨.
    E_CONFIRM_BTN.prop('onclick', null).off('click');
    E_CONFIRM_BTN.on('click', function(e){
        func();
    });
    E_CONFIRM_MODAL.modal({backdrop: 'static', keyboard: true}, 'show');
}

function delete_model(model_id) {
    confirm_modal('다음 ID의 데이터를 삭제할까요?',
        'ID: ' + model_id,
        function() {
        globalSendCommand('delete', 'id=' + model_id, null, null, function(result) {
            if (result.ret == 'success') {
                globalRequestSearch(1);
            }
        });
    });
}

function open_modal_by_id(from, model_id) {
    globalSendCommand("get", 'id=' + model_id, null, null, function(result) {
        if (result.ret == 'success') {
            open_modal(from, result.data);
        }
    });
}

// 추가 버튼
$('#add-btn').on('click', function(e) {
    e.preventDefault();
    open_modal('new', '');
});
// 저장 버튼
$('#save-btn').on('click', function() {
    let ids = $(this).data('id');
    //let formdata = getFormdata('#setting');
    let formdata = get_form_data('#setting');
    for (let i in ids) {
        formdata += '&id=' + ids[i];
    }
    globalSendCommand('save', formdata, null, null, function(result) {
        if (result.ret == 'success') {
            $('#add-modal').modal('hide');
            globalRequestSearch(1);
        }
    });
});