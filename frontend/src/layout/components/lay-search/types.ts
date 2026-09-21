interface optionsItem {
  path: string;
  type: "history" | "collect";
  meta: {
    icon?: string;
    title?: string;
    /** 186 N2：归属分区标题（结果显示用） */
    parentTitle?: string;
  };
}

interface dragItem {
  oldIndex: number;
  newIndex: number;
}

interface Props {
  value: string;
  options: Array<optionsItem>;
}

export type { optionsItem, dragItem, Props };
