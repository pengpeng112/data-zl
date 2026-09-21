import { h, defineComponent, withDirectives, resolveDirective } from "vue";

/** 封装@vueuse/motion动画库中的自定义指令v-motion */
export default defineComponent({
  name: "Motion",
  props: {
    delay: {
      type: Number,
      default: 50
    }
  },
  render() {
    const { delay } = this;
    const motion = resolveDirective("motion");
    return withDirectives(
      h(
        "div",
        {},
        {
          default: () => [this.$slots.default()]
        }
      ),
      [
          [
            motion,
            {
              // DEF-08（194）：仅做透明度淡入，不做 y 位移，避免入场后坐标漂移
              initial: { opacity: 0 },
              enter: {
                opacity: 1,
                transition: {
                  delay
                }
              }
            }
          ]
        ]
    );
  }
});
