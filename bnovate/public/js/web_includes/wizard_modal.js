
const modal_template = `
<div class="modal" tabindex="-1" role="dialog" id="myModal" style="display:none">
    <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">{{ __("Request Refill") }}</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body">
                
                <ol class="wizard-ribbon">
                    <li class="wizard-step current" data-step="1">{{ __("Cartridges") }}</li>
                    <li class="wizard-step" data-step="2">{{ __("Shipping") }}</li>
                    <li class="wizard-step" data-step="3">{{ __("Billing") }}</li>
                    <li class="wizard-step" data-step="4">{{ __("Summary") }}</li>
                </ol>
                
                <div class="wizard-page" id="page1"> 
                    <i class="fa fa-cog fa-spin" style="font-size: 20px"></i>
                </div>
                <div class="wizard-page" id="page2" style="display: none;"></div>
                <div class="wizard-page" id="page3" style="display: none;"></div>
                <div class="wizard-page wizard-summary" id="page4" style="display: none;"></div>

                <div class="modal-footer">
                    <div class="wizard-buttons">
                        <!-- <button type="button" class="btn btn-danger" id="cancelButton">{{ __("Cancel") }}</button> -->
                        <button type="button" class="btn btn-secondary" id="prev-button">{{ __("Previous") }}</button>
                        <button type="button" class="btn btn-primary" id="next-button" disabled>{{ __("Next") }}</button>
                        <button type="button" class="btn btn-primary" id="done-button">{{ __("Confirm Order") }}</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
`;

const template_page1 = `
<table class="table">
    <thead>
        <th>{{ __("Serial No") }}</th>
        <th>{{ __("Compatibility") }}</th>
        <th>{{ __("Variant") }}</th>
    </thead>
    <tbody>
        <tr>
            <td>[{{ __("All") }}]</td>
            <td></td>
            <td>
                <select id="variant-default" style="width: 50%">
                    <option value=""></option>
                    <option>TCC</option>
                    <option>ICC</option>
                    <option>ACC</option>
                    <option>CBC</option>
                </select>
            </td>
        </tr>
        {% for sn in serial_nos %}
        <tr>
            <td>{{ sn.serial_no }}</td>
            <td>{{ sn.compatibility }}</td>
            <td>
                <select class="variant-select" name="variant-{{sn.serial_no}}" data-sn="{{sn.serial_no}}" data-last_shipped="{{sn.address_short}}" style="width: 50%">
                    <option value=""></option>
                    {% if sn.item_code == "101083" %}
                        <option>ACC</option>
                        <option>CBC</option>
                    {% else %}
                        <option>TCC</option>
                        <option>ICC</option>
                    {% endif %}
                </select>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
`;

const template_page2 = `
<div class="card-group">
    {% for addr in shipping_addresses %}
    <div class="card">
        <div class="card-body">
            <input type="radio" name="shipping_address" id="ship-{{addr.name}}" value="{{addr.name}}" {% if shipping_addresses.length == 1 %}checked{% endif %}/>
            <label for="ship-{{addr.name}}">{{addr.display}}</label>
        </div>
    </div>
    {% endfor %}
</div>
`

const template_page3 = `
<div class="card-group">
    {% for addr in billing_addresses %}
    <div class="card">
        <div class="card-body">
            <input type="radio" name="billing_address" id="bill-{{addr.name}}" value="{{addr.name}}" {% if billing_addresses.length == 1 %}checked{% endif %}/>
            <label for="bill-{{addr.name}}">{{addr.display}}</label>
        </div>
    </div>
    {% endfor %}
</div>
`

const template_page4 = `
<div class="row">
    <div class="col-sm">
        <h5>{{ __("Shipping") }}</h5>
        {{doc.shipping_address_display}}
    </div>
    <div class="col-sm">
        <h5>{{ __("Billing") }}</h5>
        {{doc.billing_address_display}}
    </div>
</div>

<div class="row">
    <div class="col-sm">
        <h5>{{ __("Cartridges") }}</h5>
        <table class="table">
            <thead>
                <th>{{ __("Serial No") }}</th>
                <th>{{ __("Variant") }}</th>
                <th>{{ __("Last Shipped To") }}</th>
            </thead>
            <tbody>
                {% for it in doc.items %}
                <tr>
                    <td>{{ it.serial_no }}</td>
                    <td>{{ it.type }}</td>
                    <td>{{ it.last_shipped }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="row">
    <div class="col-sm">
        <div id="form-container">
            <form action="">
                {% if doc.organize_return %}
                <h5>{{ __("Parcel Count") }}</h5>
                <p>{{ __("How many parcels are you sending?") }}</p>
                <p>{{ __("One parcel can contain several cartridges. We will create one return label per parcel.") }}</p>
                <div class="form-group">
                    <label for="parcel_count" class="control-label" style="display: none">{{ __("Parcel Count") }}</label>
                    <input type="number" class="form-control" name="parcel_count" min="1" max="10" style="width: 30%" value="1">
                </div>
                {% endif %}

                <h5>{{ __("Your Order Reference (PO Number)") }}</h5>
                <div class="form-group">
                    <label for="remarks" style="display: none">{{ __("Purchase Order No") }}</label>
                    <input type="text" class="form-control" name="po_no">
                </div>

                <h5>{{ __("Attachments") }}</h5>
                <div class="form-group">
                    <div class="wizard-file-dropzone" data-file-dropzone>
                        <input type="file" name="attachments" multiple style="display: none">
                        <div>{{ __("Drag and drop files here, or click to browse") }}</div>
                        <small class="text-muted">{{ __("You can select multiple files") }}</small>
                    </div>
                    <div class="wizard-file-list" data-file-list></div>
                </div>

                

                <h5>{{ __("Remarks") }}</h5>
                <div class="form-group">
                    <label for="remarks" style="display: none">Remarks</label>
                    <textarea type="text" name="remarks"></textarea>
                </div>
            </form>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-sm">
    <p>{{ __("After confirming this order, the cartridges will be filled, shipped, and charged to your account.") }}</p>
    </div>
</div>
`

customElements.define('wizard-modal', class extends HTMLElement {
    constructor() {
        super();

        window.theModal = this;

        // Data used to build the refill request doc:
        this.serial_nos = [];
        this.addresses = [];
        this.doc = {};
        this.organize_return = false;
        this.parcel_count = 0;
        this.files = [];

        // Initialize the wizard
        this.currentPage = 1;
        this.numPages = 4; // $(".wizard-page").length;
    }

    draw() {
        // Attach template. Only draw when modal is summoned, makes it more likely that translations are loaded.
        this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = frappe.render_template(modal_template, {});


        this.modal = this.shadowRoot.getElementById("myModal");
        this.next = this.shadowRoot.getElementById("next-button");
        this.prev = this.shadowRoot.getElementById("prev-button");
        this.done = this.shadowRoot.getElementById("done-button");

        $(this.modal).on('show.bs.modal', (e) => {
            this.currentPage = 1;
            this.show_page(this.currentPage);

            e.target.querySelector('.modal-body #page1').innerHTML = frappe.render_template(template_page1, {
                serial_nos: this.serial_nos,
            });
            e.target.querySelector('.modal-body #page2').innerHTML = frappe.render_template(template_page2, {
                shipping_addresses: this.shipping_addresses,
            });
            e.target.querySelector('.modal-body #page3').innerHTML = frappe.render_template(template_page3, {
                billing_addresses: this.billing_addresses,
            });

            this.bind_listeners(e.target);
        })

        $(this.modal).on('hide.bs.modal', (e) => {
            // e.target.querySelector('.modal-body #page1').innerHTML = '';
        })

        // Add event listeners to the navigation buttons
        $(this.prev).click(() => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.show_page(this.currentPage);
            }
        });

        $(this.next).click(() => {
            if (this.currentPage < this.numPages) {
                this.currentPage++;
                this.show_page(this.currentPage);
            }
        });

        $(this.cancel).click(() => {
            // Close the modal or redirect to another page
            $(this.modal).modal("hide");
        });

        $(this.done).click(() => {
            this.confirm();
        });
    }

    show(serial_nos, address_data, organize_return, callback) {
        if (!this.shadowRoot) {
            this.draw();
        }
        this.serial_nos = serial_nos;
        this.addresses = address_data.addresses;
        this.shipping_addresses = address_data.shipping_addresses;
        this.billing_addresses = address_data.billing_addresses;
        this.organize_return = organize_return;
        this.callback = callback;
        $(this.modal).modal({ backdrop: 'static', keyboard: false });
    }

    hide() {
        $(this.modal).modal('hide');
    }

    // Show or hide the navigation buttons based on the current page
    update_buttons() {
        if (this.currentPage == 1) {
            this.prev.disabled = true;
        } else {
            this.prev.disabled = false;
        }

        if (this.currentPage == this.numPages) {
            this.next.hidden = true;
            this.done.hidden = false;
        } else {
            this.next.hidden = false;
            this.done.hidden = true;
        }

        $(".wizard-step").removeClass("current");
        $(`.wizard-step[data-step='${this.currentPage}']`).addClass("current");
    }

    // Enable or disable buttons based on form completion
    enable_buttons() {
        const doc = this.build_doc()

        if (this.currentPage == 1) {
            if (doc.items.length && doc.items.findIndex(el => el.type == '') < 0) {
                this.next.disabled = false;
            } else {
                this.next.disabled = true;
            }
        } else if (this.currentPage == 2) {
            if (doc.shipping_address) {
                this.next.disabled = false;
            } else {
                this.next.disabled = true;
            }
        } else if (this.currentPage == 3) {
            if (doc.billing_address) {
                this.next.disabled = false;
            } else {
                this.next.disabled = true;
            }
        }
    }

    // Show the specified page and update the navigation buttons
    show_page(page) {
        if (page == this.numPages) {
            this.modal.querySelector('#page' + page).innerHTML = frappe.render_template(
                template_page4,
                { doc: this.build_doc() }
            );
        }

        $(".wizard-page").hide();
        $("#page" + page).show();

        this.update_buttons();
        this.enable_buttons();
    }

    // Set all variant selects when the first one is modified, only if variant is compatible
    bind_listeners(el) {
        const selects = [...el.querySelectorAll(".variant-select")];
        el.querySelector("#variant-default").addEventListener("change", (e) => {
            selects.forEach(s => {
                if ([...s.options].some(opt => opt.value === e.target.value)) {
                    s.value = e.target.value;
                }
            });
            this.enable_buttons();
        })

        selects.map(s => s.addEventListener('change', () => this.enable_buttons()));
        [...el.querySelectorAll("input")].map(i => i.addEventListener("change", () => this.enable_buttons()));

        const dropzone = el.querySelector("[data-file-dropzone]");
        const file_input = dropzone?.querySelector("input[type='file']");
        const file_list = el.querySelector("[data-file-list]");
        if (dropzone && file_input) {
            const add_files = (files) => {
                this.files = [...this.files, ...files];
                file_list.innerHTML = this.files.map(file =>
                    `<div>${frappe.utils.escape_html(file.name)} <small class="text-muted">(${Math.ceil(file.size / 1024)} KB)</small></div>`
                ).join("");
            };
            dropzone.addEventListener("click", () => file_input.click());
            file_input.addEventListener("change", (event) => add_files([...event.target.files]));
            ["dragenter", "dragover"].forEach(event_name => dropzone.addEventListener(event_name, (event) => {
                event.preventDefault();
                dropzone.classList.add("border-primary");
            }));
            ["dragleave", "drop"].forEach(event_name => dropzone.addEventListener(event_name, (event) => {
                event.preventDefault();
                dropzone.classList.remove("border-primary");
            }));
            dropzone.addEventListener("drop", (event) => add_files([...event.dataTransfer.files]));
        }
    }

    build_doc() {
        const items = [...this.modal.querySelectorAll(".variant-select")].map(el => ({
            serial_no: el.dataset.sn,
            last_shipped: el.dataset.last_shipped,
            type: el.value,
        }));
        const shipping_address = this.modal.querySelector("input[name='shipping_address']:checked")?.value;
        const billing_address = this.modal.querySelector("input[name='billing_address']:checked")?.value;
        const parcel_count = this.modal.querySelector("input[name='parcel_count']")?.value;
        const po_no = this.modal.querySelector("input[name='po_no']")?.value;
        const remarks = this.modal.querySelector("textarea[name='remarks']")?.value;

        const shipping_address_display = this.addresses.find(addr => addr.name == shipping_address)?.display;
        const billing_address_display = this.addresses.find(addr => addr.name == billing_address)?.display;

        const doc = {
            items,
            shipping_address,
            shipping_address_display,
            billing_address,
            billing_address_display,
            po_no,
            remarks,
            organize_return: this.organize_return,
            parcel_count,
            files: this.files,
        };
        return doc;
    }

    confirm() {
        this.callback(this.build_doc());
        this.hide();
    }
})