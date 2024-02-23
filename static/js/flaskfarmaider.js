function init() {
    E_CONFIRM_TITLE = $('#confirm_title');
    E_CONFIRM_BODY = $('#confirm_body');
    E_CONFIRM_BTN = $('#confirm_button');
    E_CONFIRM_MODAL = $("#confirm_modal");

    E_SELECT_ALL = $('#select-all');
    E_SELECT_ALL.on('click', function(e) {
        /*
        console.log($(this).hasClass('active'));
        if ($(this).hasClass('active')) {
            $('input[class="selectable"]').each(function() {
                this.checked = false;
            });
        } else {
            $('input[class="selectable"]').each(function() {
                this.checked = true;
            });
        }
        */
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
}

function pagination(target, page, total, limit, list_func) {
    target.empty();
    limit_page = 10;
    final_page = Math.ceil(total / limit);
    if (final_page > 1) {
        first_page = Math.floor(page / limit_page) * limit_page;
        if (page < limit_page) {
            first_page++;
        }
        last_page = Math.min(first_page + limit_page, final_page);
        elements = '<ul class="pagination justify-content-center">';
        if (first_page >= limit_page) {
            elements += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>';
        }
        elements += '<li class="page-item' + (first_page < limit_page ? ' disabled' : '') + '">';
        elements += '<a class="page-link" aria-label="Previous" data-page="' + (first_page - 1) + '"><span aria-hidden="true">&laquo;</span></a></li>';
        for (i = first_page; i <= last_page; i++) {
            elements += '<li class="page-item' + (i == page ? ' active" aria-current="page"' : '"') + '>';
            elements += '<a class="page-link" href="#" data-page="' + i + '">' + i + '</a></li>';
        }
        elements += '<li class="page-item' + (last_page >= final_page ? ' disabled' : '') + '">';
        elements += '<a class="page-link" href="#" aria-label="Next" data-page="' + (last_page + 1) +'"><span aria-hidden="true">&raquo;</span></a></li>';
        if (last_page < final_page) {
            elements += '<li class="page-item"><a class="page-link" href="#" data-page="' + final_page + '">' + final_page + '</a></li></ul>';
        }
    } else {
        elements = '<ul class="pagination justify-content-center">';
        elements += '<li class="page-item disabled"><a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a></li>';
        elements += '<li class="page-item disabled"><a class="page-link disabled" href="#">1</a></li>';
        elements += '<li class="page-item disabled"><a class="page-link" href="#"  aria-label="Next"><span aria-hidden="true">&raquo;</span></a></li></ul>';
    }
    target.append(elements);
    $('.page-link').on('click', function(e) {
        list_func($(this).data('page'));
    });
}

function confirm_modal(title, content, func) {
    E_CONFIRM_TITLE.html(title);
    E_CONFIRM_BODY.html(content);
    // 클릭 이벤트가 bubble up 되면서 중복 실행됨 e.stopImmediatePropagation(); 로 해결 안 됨.
    E_CONFIRM_BTN.prop('onclick', null).off('click');
    E_CONFIRM_BTN.on('click', function(e){
        func();
    });
    E_CONFIRM_MODAL.modal();
}

function copy_to_clipboard(text) {
    if ( ! window.navigator.clipboard ) {
        notify('클립보드 접근 권한이 없습니다.', 'warning');
    } else {
        window.navigator.clipboard.writeText(text).then(() => {
            notify('클립보드에 복사하였습니다.', 'success');
        },() => {
            notify('클립보드 복사에 실패했습니다.', 'warning');
        });
    }
}

function set_plex_sections(type, target) {
    target.empty();
    if (SECTIONS[type]) {
        SECTIONS[type].forEach(function(item) {
            target.append(
                $('<option></option>').prop('value', item.id).append(item.name)
            );
        });
    } else {
        console.error('type: ' + type);
        console.error(SECTIONS);
        notify('라이브러리 섹션 정보가 없습니다.', 'warning');
        target.append('<option>정보 없음</option>');
    }
    target.prop('value', '');
}
