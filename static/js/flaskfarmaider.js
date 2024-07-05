// FF의 confirm 모달은 플러그인의 콘텐츠보다 늦게 출력되기 때문에 documnet ready 후에 셀렉터 사용
const E_CONFIRM_TITLE = $('#confirm_title');
const E_CONFIRM_BODY = $('#confirm_body');
const E_CONFIRM_BTN = $('#confirm_button');
const E_CONFIRM_MODAL = $("#confirm_modal");
const E_SELECT_ALL = $('#select-all');
const E_MULTIPLE_DEL = $('#multiple-del');
const E_MULTIPLE_EDIT = $('#multiple-edit');
const SOCKET = io.connect(window.location.href);

function confirmModal(title, content, func) {
    E_CONFIRM_TITLE.html(title);
    E_CONFIRM_BODY.html(content);
    E_CONFIRM_BTN.off('click');
    E_CONFIRM_BTN.on('click', func);
    E_CONFIRM_MODAL.modal({backdrop: 'static', keyboard: true}, 'show');
}

function deleteModel(model_id) {
    confirmModal('다음 ID의 데이터를 삭제할까요?',
        'ID: ' + model_id,
        function() {
        globalSendCommand('delete', 'id=' + model_id, null, null, function(result) {
            if (result.ret == 'success') {
                globalRequestSearch(1);
            }
        });
    });
}

function openModalById(from, model_id) {
    globalSendCommand("get", 'id=' + model_id, null, null, function(result) {
        if (result.ret == 'success') {
            openModal(from, result.data);
        }
    });
}

function setPlexSections(type, target, sections) {
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

function pagination(target, page, total, limit, listFunc) {
    target.empty();
    let limit_page = 10;
    let final_page = Math.ceil(total / limit);
    if (final_page > 1) {
        let first_page = Math.floor(page / limit_page) * limit_page;
        if (page < limit_page) {
            first_page++;
        }
        let last_page = Math.min(first_page + limit_page, final_page);
        let elements = '<ul class="pagination justify-content-center">';
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
        listFunc($(this).data('page'));
    });
}

function copyToClipboard(text) {
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

function joinBy(itemList, delimiter = '\r\n') {
    let list_ = JSON.parse(itemList);
    if (list_ !== null) {
        return list_.join(delimiter);
    } else {
        return '';
    }
}

function renderAddableInputGroup(itemList, groupId, formName, placeHolder) {
    const ADDABLE_GROUP = $('#' + groupId);
    let defaultInputGroup = '<div class="input-group">';
    defaultInputGroup += '<input name="' + formName + '" class="form-control form-control-sm" type="text" placeholder="' + placeHolder + '">'
    defaultInputGroup += '<button type="button" class="btn btn-outline-warning btn-sm btn-remove-element">삭제</button>';
    defaultInputGroup += '</div>';
    if (itemList.length < 1) {
        let inputGroup = $(defaultInputGroup);
        inputGroup.children('.btn-remove-element').remove();
        inputGroup.append('<button type="button" class="btn btn-outline-primary btn-sm btn-add-element">추가</button>');
        inputGroup.children('input').prop('value', '');

        inputGroup.on('click', '.btn-add-element', function() {
            let addingInputGroup = $(defaultInputGroup);
            addingInputGroup.on('click', '.btn-remove-element', function() {
                $(this).parent().remove();
            });
            ADDABLE_GROUP.append(addingInputGroup);
        });
        ADDABLE_GROUP.append(inputGroup);

    } else {
        for (let idx in itemList) {
            let inputGroup = $(defaultInputGroup);
            if (idx < 1) {
                inputGroup.children('.btn-remove-element').remove();
                inputGroup.append('<button type="button" class="btn btn-outline-primary btn-sm btn-add-element">추가</button>');
                inputGroup.on('click', '.btn-add-element', function() {
                    let addingInputGroup = $(defaultInputGroup);
                    addingInputGroup.on('click', '.btn-remove-element', function() {
                        $(this).parent().remove();
                    });
                    ADDABLE_GROUP.append(addingInputGroup);
                });
            }
            inputGroup.children('input').prop('value', itemList[idx]);
            inputGroup.on('click', '.btn-remove-element', function() {
                $(this).parent().remove();
            });
            ADDABLE_GROUP.append(inputGroup);
        }
    }
}

// 추가 버튼
$('#add-btn').on('click', function(e) {
    e.preventDefault();
    openModal('new', '');
});

// 저장 버튼
$('#save-btn').on('click', function() {
    let ids = $(this).data('id');
    let formdata = new FormData(document.getElementById('setting'));
    let checkboxes = ['sch-recursive', 'sch-schedule-auto-start']
    for (idx in checkboxes) {
        if ($('#' + checkboxes[idx] + '-helper').prop('checked')) {
            if (!$('#' + checkboxes[idx]).prop('checked')) {
                formdata.append(checkboxes[idx], 'off');
            }
        }
    }
    for (let i in ids) {
        formdata.append('id', ids[i]);
    }
    let query = new URLSearchParams(formdata).toString();
    console.log(query);
    globalSendCommand('save', query, null, null, function(result) {
        if (result.ret == 'success') {
            $('#add-modal').modal('hide');
            globalRequestSearch(1);
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

SOCKET.on('result', function(result) {
    if (result) {
        if (result.data.msg) {
            notify(result.data.msg, 'info');
        }
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
