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
