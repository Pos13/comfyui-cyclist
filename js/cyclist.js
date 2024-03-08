import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { $el } from "../../../scripts/ui.js";

var cyclist_states = {}

function drawBadge(ctx, text, color="green") {
    if (text) {
        // Badge in pythongosssss/WD14 style
        ctx.save()
        ctx.font = "12px sans-serif"
        const sz = ctx.measureText(text)
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.roundRect(0, -LiteGraph.NODE_TITLE_HEIGHT - 20, sz.width + 12, 20, 5)
        ctx.fill()
        ctx.fillStyle = "white"
        ctx.fillText(text, 6, -LiteGraph.NODE_TITLE_HEIGHT - 6)
        ctx.restore()
    }
}

app.registerExtension({
    name: "comfyui.cyclist",
    async setup() {
        function popupMessageHandler(event) {
            if (event.detail.stop) {
                app.ui.dialog.show(event.detail.message)
                cyclist_states["InterruptNode"+app.runningNodeId] = "Interrupt was here!"
                if (app.ui.autoQueueMode === "instant") {
                    // Prevent short circuit in "insant" mode: queue, interrupt, queue, interrupt...
                    app.ui.autoQueueEnabled = false
                    let auto_queue_checkbox = document.getElementById("autoQueueCheckbox")
                    if(auto_queue_checkbox) auto_queue_checkbox.checked = false;
                }
            }
            else cyclist_states["InterruptNode"+app.runningNodeId] = null
        }
        api.addEventListener("cyclist.message.popup", popupMessageHandler);

        function updateTimerHandler(event) {
            let postfix = event.detail.mode.charAt(0)
            let rounding = 2
            if (event.detail.mode === "milliseconds") rounding = 0;
            let last_time = `${event.detail.last_time.toFixed(rounding)}${postfix}`
            let total_time = `${event.detail.total_time.toFixed(rounding)}${postfix}`
            cyclist_states[event.detail.loop_id+".LoopTimer"] = `${last_time} | ${total_time}`
        }
        api.addEventListener("cyclist.timer.update", updateTimerHandler);

        const btns = document.querySelector(".comfy-menu-btns")
        $el("button", {
            id: "cyclist-new-cycle-button",
            textContent: "New Cycle",
            parent: btns,
            onclick: newCycle
        });
        async function newCycle() {
            let already_incremented = []
            for (var node_index in app.graph._nodes) {
                let c_node = app.graph._nodes[node_index]
                let c_node_prototype = Object.getPrototypeOf(c_node)
                if (c_node_prototype.IS_CYCLIST_IO) {
                    // - if it's disconnected or widget - increment loop id
                    // - if connected to other node - don't increment
                    // - except it's Primitive or Const - increment that node's widget directly
                    let new_value = ""
                    let connected = false
                    if (c_node && c_node.inputs) {
                        let loop_input = c_node.inputs.find((i) => i.name === "loop_id" || i.name === "filename");
                        if (loop_input && loop_input.link) {
                            let loop_link = app.graph.links[loop_input.link]
                            if (loop_link) {
                                let origin_node = app.graph._nodes_by_id[loop_link.origin_id]
                                if (origin_node && origin_node.type === "PrimitiveNode") {
                                    let value_widget = origin_node?.widgets.find((w) => w.name === "value")
                                    new_value = replace_counter(value_widget.value)
                                    if (!already_incremented.includes(loop_link.origin_id)) {
                                        value_widget.value = new_value
                                        already_incremented.push(loop_link.origin_id)
                                        origin_node.onResize?.(origin_node.size) // Redraw
                                    }
                                } else {
                                    connected = true
                                }
                            }
                        }
                    }
                    let loop_id_widget = c_node?.widgets.find((w) => w.name === "loop_id" || w.name === "filename");
                    if (!connected && loop_id_widget && !already_incremented.includes(c_node.id)) {
                        if (new_value === "") new_value = replace_counter(loop_id_widget.value);
                        loop_id_widget.value = new_value
                        already_incremented.push(c_node.id)
                        c_node.onResize?.(c_node.size)
                    }
                }
            }
            function replace_counter(str) {
                let counter = str.match(/\d+$/)
                if (counter) return str.replace(/\d+$/, String(parseInt(counter) + 1))
                else return str + "_2";
            }
        }
    },

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.category === "cyclist/Write") {
            nodeType.prototype.IS_CYCLIST_IO = true

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
				onExecuted?.apply(this, arguments)
                let state = "Iteration: " + String(message.counter[0])
                //let state_id_node = String(this.id)
                //cyclist_states[state_id_node] = state

                let to_memory_input = this.inputs?.find((i) => i.name === "to_memory")
                if (!to_memory_input && this.inputs && this.inputs.length > 0) to_memory_input = this.inputs[0];
                if (to_memory_input) {
                    let state_id_loop = message.loop_id[0] + "." + to_memory_input.type
                    cyclist_states[state_id_loop] = state
                }
			};
            const onDrawForeground = nodeType.prototype.onDrawForeground;
		    nodeType.prototype.onDrawForeground = function (ctx) {
                const r = onDrawForeground?.apply?.(this, arguments)
                
                let state_id_loop = null
                let loop_id_widget = this.widgets?.find((w) => w.name === 'loop_id')
                if (!loop_id_widget) loop_id_widget = this.widgets?.find((w) => w.name === 'filename');
                let to_memory_input = this.inputs?.find((i) => i.name === "to_memory")
                if (!to_memory_input && this.inputs && this.inputs.length > 0) to_memory_input = this.inputs[0];
                if (loop_id_widget && to_memory_input) state_id_loop = loop_id_widget.value + "." + to_memory_input.type;
                
                if (state_id_loop) drawBadge(ctx, cyclist_states[state_id_loop])
                //if (!state) state = cyclist_states[String(this.id)]

                return r
            }
        }
        if (nodeData.category === "cyclist/Read") {
            nodeType.prototype.IS_CYCLIST_IO = true

            const onDrawForeground = nodeType.prototype.onDrawForeground;
		    nodeType.prototype.onDrawForeground = function (ctx) {
                const r = onDrawForeground?.apply?.(this, arguments)
                
                let state_id_loop = null
                let loop_id_widget = this.widgets?.find((w) => w.name === 'loop_id')
                if (!loop_id_widget) loop_id_widget = this.widgets?.find((w) => w.name === 'filename');
                let to_memory_output = null
                if (this.outputs && this.outputs.length > 0) to_memory_output = this.outputs[0];
                if (loop_id_widget && to_memory_output) state_id_loop = loop_id_widget.value + "." + to_memory_output.type;
                
                let state = null
                if (state_id_loop) state = cyclist_states[state_id_loop]
                //if (!state) state = cyclist_states[String(this.id)]
                
                drawBadge(ctx, state)
                return r
            }
        }
        if (nodeData.name === "CyclistTimer") {
            nodeType.prototype.IS_CYCLIST_IO = true

            const onDrawForeground = nodeType.prototype.onDrawForeground;
		    nodeType.prototype.onDrawForeground = function (ctx) {
                const r = onDrawForeground?.apply?.(this, arguments)
                
                let state_id_loop = null
                let loop_id_widget = this.widgets?.find((w) => w.name === 'loop_id')
                if (loop_id_widget) state_id_loop = loop_id_widget.value + ".LoopTimer";
                
                if (state_id_loop) drawBadge(ctx, cyclist_states[state_id_loop])
                //if (!state) state = cyclist_states[String(this.id)]
                
                return r
            }
        }
        if (nodeData.name === "CyclistTimerStop") {
            nodeType.prototype.IS_CYCLIST_IO = true
        }
        if (nodeData.name === "Interrupt") {
            const onDrawForeground = nodeType.prototype.onDrawForeground;
		    nodeType.prototype.onDrawForeground = function (ctx) {
                const r = onDrawForeground?.apply?.(this, arguments)
                
                let state = null
                if (cyclist_states["InterruptNode"+this.id]) state = cyclist_states["InterruptNode"+this.id];
                let stop_widget = this.widgets?.find((w) => w.name === 'stop')
                let stop_input = this.inputs.find((i) => i.name === "stop");
                if (stop_widget && !stop_input) {
                    if (stop_widget.value === true) state = "Will interrupt!";
                    else state = null
                }
                
                drawBadge(ctx, state, "red")

                return r
            }

            nodeType.prototype.computeSize = () => [150, 60] // Hardcoded min width/height

            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            // type: input/output=1/2; index=0/1/2/...; connected: connect/disconnect=true/false; link_info.origin_id=other node id
            nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
                if (index === 0) {
                    let input = this.inputs[0]
                    let output = this.outputs[0]

                    function Reset(input, output) {
                        if (input) {
                            input.type = "*"
                        }
                        if (output) {
                            output.type = "*"
                            output.name = "*"
                        }
                    }

                    if ((type === LiteGraph.OUTPUT && !input.link) || (type === LiteGraph.INPUT && (!output.links || output.links.length === 0))) {
                        // Return to default on full disconnect
                        if (!connected) {
                            Reset(input, output)
                        } else {
                            // New input, empty output
                            if (type === LiteGraph.INPUT) {
                                try {
                                    let app_link = app.graph.links[input.link]
                                    let input_node = app.graph.getNodeById(app_link.origin_id)
                                    let node_output_slot = input_node.outputs[app_link.origin_slot]
                                    let new_type = node_output_slot.type
                                    output.type = new_type
                                    output.name = new_type
                                } catch (error) {
                                    Reset(null, output)
                                }
                            // New output, empty input
                            } else {
                                try {
                                    let app_link = app.graph.links[link_info.id]
                                    let output_node = app.graph.getNodeById(app_link.target_id)
                                    let node_input_slot = output_node.inputs[app_link.target_slot]
                                    let new_type = node_input_slot.type
                                    input.type = new_type
                                } catch (error) {
                                    Reset(input, null)
                                }
                            }
                        }
                    }
                    input.color_on = LGraphCanvas.link_type_colors[input.type]
                    output.color_on = LGraphCanvas.link_type_colors[output.type]
                }
                return onConnectionsChange?.apply(this, arguments);
            }
        }
    },

    async nodeCreated(node, app) {
        if (node.comfyClass === "Interrupt") node.setSize([150, 60]);
    }
})