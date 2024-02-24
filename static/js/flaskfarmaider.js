function set_plex_sections(type, target, sections) {
    target.empty();
    if (sections[type]) {
        sections[type].forEach(function(item) {
            target.append(
                $('<option></option>').prop('value', item.id).append(item.name)
            );
        });
    } else {
        console.error('type: ' + type);
        console.error(sections);
        notify('라이브러리 섹션 정보가 없습니다.', 'warning');
        target.append('<option>정보 없음</option>');
    }
    target.prop('value', '');
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

function build_form_header(title, col) {
    let element = '<div class="row" style="padding-top: 10px; padding-bottom:10px; align-items: center;"><div class="col-sm-3 set-left">';
    element += '<strong>' + title + '</strong></div>';
    element += '<div class="col-sm-9">';
    element += '<div class="input-group col-sm-' + col + '">';
    return element;
}

function build_form_footer(desc) {
    let element = '</div><div class="col-sm-9"><em>' + desc + '</em>';
    element += '</div></div></div>';
    return element;
}

function build_form_select(id, title, options, col, desc) {
    let element = build_form_header(title, col);
    element += '<select id="' + id + '" name="' + id + '" class="form-control form-control-sm">';
    if (options.length > 0) {
        for (let idx in options) {
            element += '<option value="' + options[idx].value + '">' + options[idx].name + '</option>';
        }
    }
    element += '</select>';
    element += build_form_footer(desc);
    return element;
}

function build_form_text(id, title, value, col, desc) {
    let element = build_form_header(title, col);
    element += '<input id="' + id + '" name="' + id + '" type="text" class="form-control form-control-sm" value="' + value + '" />';
    element += build_form_footer(desc);
    return element;
}

function build_form_text_btn(id, title, value, btn_id, btn_text, col, desc) {
    let element = build_form_header(title, col);
    element += '<input id="' + id + '" name="' + id + '" type="text" class="form-control form-control-sm" value="' + value + '" />';
    element += '<div class="btn-group btn-group-sm flex-wrap mr-2" role="group" style="padding-left:5px; padding-top:0px">';
    element += '<button id="' + btn_id + '" class="btn btn-sm btn-outline-primary">' + btn_text + '</button></div>';
    element += build_form_footer(desc);
    return element;
}

function build_form_checkbox(id, title, options, col, desc) {
    let element = build_form_header(title, col);
    element += '<input id="' + id + '" name="' + id + '" type="checkbox" class="form-control form-control-sm" data-toggle="toggle" />';
    element += '<select id="' + id + '-select" name="' + id + '-select" class="form-control form-control-sm col-sm-2">';
    if (options.length > 0) {
        for (let idx in options) {
            element += '<option value="' + options[idx].value + '">' + options[idx].name + '</option>';
        }
    }
    element += '</select>';
    element += build_form_footer(desc);
    return element;
}

function build_form_radio(id, title, options, col, desc) {
    let element = build_form_header(title, col);
    for (let idx in options) {
        element += '<div class="custom-control custom-radio custom-control-inline">';
        element += '<input id="'+ id + idx + '" type="radio" class="custom-control-input" name="' + id + '" value="' + options[idx].value +'">';
        element += '<label class="custom-control-label" for="' + id + idx + '">' + options[idx].name + '</label></div>';
    }
    element += build_form_footer(desc);
    return element;
}

function build_form_group(id, elements) {
    let element = '<div id="' + id + '">';
    for (let idx in elements) {
        element += elements[idx];
    }
    element += '</div';
    return element
}