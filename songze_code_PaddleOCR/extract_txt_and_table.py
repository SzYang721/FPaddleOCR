import argparse
import os
import pdfplumber
import json
from collections import defaultdict
import re  # Import the re module

def convert_table_to_markdown(data):
    markdown_table = "| " + " | ".join(str(item) for item in data[0]) + " |\n"  # Header
    markdown_table += "| " + "--- | " * len(data[0]) + "\n"  # Separator
    for row in data[1:]:
        markdown_table += "| " + " | ".join(str(item) for item in row) + " |\n"
    return markdown_table + "\n\n\n"


def merge_data_sim(list_input):
    merged_list = []
    current_group = []
    for sub_list in list_input:
        if not current_group:  # Add first sub-list
            current_group.append(sub_list)
        elif len(sub_list) == len(current_group[-1]):  # Same length
            current_group.append(sub_list)
        else:
            merged_list.append(current_group)
            current_group = [sub_list]
    if current_group:
        merged_list.append(current_group)
    return merged_list


def merge_data(list_input):
    merged_list = []
    temp_table_list = []
    for item in list_input:
        if "table" in item.keys():
            temp_table_list.append(item)
        elif "text" in item.keys():
            if temp_table_list:
                cur_table_list = []
                for i in temp_table_list:
                    cur_table_list += i["table"]
                res = merge_data_sim(cur_table_list)
                for j in res:
                    merged_list.append({"table": j})
                temp_table_list = []
            merged_list.append(item)
    if temp_table_list:
        cur_table_list = []
        for item in temp_table_list:
            cur_table_list += item["table"]
        merged_list.append({"table": cur_table_list})
    return merged_list


class PDFProcessor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.pdf = pdfplumber.open(filepath)
        self.all_text = defaultdict(dict)
        self.merge_list = []
        self.allrow = 0
        self.last_num = 0
        print(f"Initialized PDFProcessor for {filepath}")

    def check_lines(self, page, top, bottom):
        lines = page.extract_words()
        text = ""
        last_top = 0
        last_check = 0
        for l in range(len(lines)):
            each_line = lines[l]
            check_re = "(?:。|；|单位：元|单位：万元|币种：人民币|\d|报告(?:全文)?(?:（修订版）|（修订稿）|（更正后）)?)$"
            if top == "" and bottom == "":
                if abs(last_top - each_line["top"]) <= 2:
                    text = text + each_line["text"]
                elif (
                    last_check > 0
                    and (page.height * 0.9 - each_line["top"]) > 0
                    and not re.search(check_re, text)
                ):
                    text = text + each_line["text"]
                else:
                    text = text + "\n" + each_line["text"]
            elif top == "":
                if each_line["top"] > bottom:
                    if abs(last_top - each_line["top"]) <= 2:
                        text = text + each_line["text"]
                    elif (
                        last_check > 0
                        and (page.height * 0.85 - each_line["top"]) > 0
                        and not re.search(check_re, text)
                    ):
                        text = text + each_line["text"]
                    else:
                        text = text + "\n" + each_line["text"]
            else:
                if each_line["top"] < top and each_line["top"] > bottom:
                    if abs(last_top - each_line["top"]) <= 2:
                        text = text + each_line["text"]
                    elif (
                        last_check > 0
                        and (page.height * 0.85 - each_line["top"]) > 0
                        and not re.search(check_re, text)
                    ):
                        text = text + each_line["text"]
                    else:
                        text = text + "\n" + each_line["text"]
            last_top = each_line["top"]
            last_check = each_line["x1"] - page.width * 0.85

        return text

    def drop_empty_cols(self, data):
        transposed_data = list(map(list, zip(*data)))
        filtered_data = [
            col for col in transposed_data if not all(cell == "" for cell in col)
        ]
        result = list(map(list, zip(*filtered_data)))
        return result

    @staticmethod
    def keep_visible_lines(obj):
        if obj["object_type"] == "rect":
            return obj["non_stroking_color"] is not None and (obj["width"] >= 1 or obj["height"] >= 1)
        if obj["object_type"] == "char":
            return obj["stroking_color"] is not None and obj["non_stroking_color"] is not None
        return True

    def extract_text_and_tables(self, page):
        bottom = 0
        page = page.filter(self.keep_visible_lines)
        tables = page.find_tables()
        if len(tables) >= 1:
            print(f"Found {len(tables)} tables on page {page.page_number}")
            count = len(tables)
            for table in tables:
                if table.bbox[3] < bottom:
                    pass
                else:
                    count -= 1
                    top = table.bbox[1]
                    text = self.check_lines(page, top, bottom)
                    text_list = text.split("\n")
                    for _t in range(len(text_list)):
                        self.all_text[self.allrow] = {
                            "page": page.page_number,
                            "allrow": self.allrow,
                            "type": "text",
                            "inside": text_list[_t],
                        }
                        self.allrow += 1

                    bottom = table.bbox[3]
                    new_table = table.extract()
                    r_count = 0
                    for r in range(len(new_table)):
                        row = new_table[r]
                        if row[0] is None:
                            r_count += 1
                            for c in range(len(row)):
                                if row[c] is not None and row[c] not in ["", " "]:
                                    if new_table[r - r_count][c] is None:
                                        new_table[r - r_count][c] = row[c]
                                    else:
                                        new_table[r - r_count][c] += row[c]
                                    new_table[r][c] = None
                        else:
                            r_count = 0

                    end_table = []
                    for row in new_table:
                        if row[0] != None:
                            cell_list = []
                            cell_check = False
                            for cell in row:
                                if cell != None:
                                    cell = cell.replace("\n", "")
                                else:
                                    cell = ""
                                if cell != "":
                                    cell_check = True
                                cell_list.append(cell)
                            if cell_check:
                                end_table.append(cell_list)

                    for row in end_table:
                        self.all_text[self.allrow] = {
                            "page": page.page_number,
                            "allrow": self.allrow,
                            "type": "excel",
                            "inside": str(row),
                        }
                        self.allrow += 1

                    if count == 0:
                        text = self.check_lines(page, "", bottom)
                        text_list = text.split("\n")
                        for _t in range(len(text_list)):
                            self.all_text[self.allrow] = {
                                "page": page.page_number,
                                "allrow": self.allrow,
                                "type": "text",
                                "inside": text_list[_t],
                            }
                            self.allrow += 1

        else:
            text = self.check_lines(page, "", "")
            text_list = text.split("\n")
            for _t in range(len(text_list)):
                self.all_text[self.allrow] = {
                    "page": page.page_number,
                    "allrow": self.allrow,
                    "type": "text",
                    "inside": text_list[_t],
                }
                self.allrow += 1

        first_re = "[^计](?:报告(?:全文)?(?:（修订版）|（修订稿）|（更正后）)?)$"
        end_re = "^(?:\d|\\|\/|第|共|页|-|_| ){1,}"
        if self.last_num == 0:
            try:
                first_text = str(self.all_text[1]["inside"])
                end_text = str(self.all_text[len(self.all_text) - 1]["inside"])
                if re.search(first_re, first_text) and not "[" in end_text:
                    self.all_text[1]["type"] = "页眉"
                    if re.search(end_re, end_text) and not "[" in end_text:
                        self.all_text[len(self.all_text) - 1]["type"] = "页脚"
            except:
                print(page.page_number)
        else:
            try:
                first_text = str(self.all_text[self.last_num + 2]["inside"])
                end_text = str(self.all_text[len(self.all_text) - 1]["inside"])
                if re.search(first_re, first_text) and "[" not in end_text:
                    self.all_text[self.last_num + 2]["type"] = "页眉"
                if re.search(end_re, end_text) and "[" not in end_text:
                    self.all_text[len(self.all_text) - 1]["type"] = "页脚"
            except:
                print(page.page_number)

        self.last_num = len(self.all_text) - 1

    def process_pdf(self):
        print(f"Processing {self.filepath}...")
        for i in range(len(self.pdf.pages)):
            print(f"Processing page {i + 1} of {len(self.pdf.pages)}")
            self.extract_text_and_tables(self.pdf.pages[i])

    def save_all_text(self, path):
        print(f"Saving extracted text to {path}")
        with open(path, "w", encoding="utf-8") as file:
            for key in self.all_text.keys():
                file.write(json.dumps(self.all_text[key], ensure_ascii=False) + "\n")

    def convert2txt(self):
        print(f"Converting extracted content to text and markdown...")
        import ast

        all_txt_dic_list = []
        for key in self.all_text.keys():
            if (
                self.all_text[key]["type"] == "text"
                and self.all_text[key]["inside"] != ""
            ):
                all_txt_dic_list.append({"text": self.all_text[key]["inside"]})
            elif self.all_text[key]["type"] == "excel":
                all_txt_dic_list.append(
                    {"table": [ast.literal_eval(self.all_text[key]["inside"])]}
                )
        self.merge_list = merge_data(all_txt_dic_list)

    def save_all_txt(self, path):
        print(f"Saving final merged text and tables to {path}")
        with open(path, "w", encoding="utf-8") as file:
            for item in self.merge_list:
                if item.get("text"):
                    file.write(item["text"] + "\n")
                if item.get("table"):
                    file.write(convert_table_to_markdown(item["table"]))

    def save_txt_and_table(self):
        print(f"Saving separate text and table files for {self.filepath}")
        import os
        fnw_text = os.path.splitext(self.filepath)[0] + ".txt"
        fnw_table = os.path.splitext(self.filepath)[0] + "_table.txt"
        
        print(f"Text will be saved to: {fnw_text}")
        print(f"Table will be saved to: {fnw_table}")

        try:
            with open(fnw_text, "w", encoding="utf-8") as file1, open(
                fnw_table, "w", encoding="utf-8"
            ) as file2:
                for i, item in enumerate(self.merge_list):
                    if item.get("text"):
                        file1.write(item["text"] + "\n")
                    if item.get("table"):
                        for j in range(4, 0, -1):
                            if i - j >= 0 and self.merge_list[i - j].get("text"):
                                file2.write(self.merge_list[i - j]["text"] + "\n")
                        file2.write(convert_table_to_markdown(item["table"]))
            print(f"Successfully saved text and table files for {self.filepath}")
        except Exception as e:
            print(f"Failed to save files for {self.filepath}: {e}")



def process_directory(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, input_dir)
                output_subdir = os.path.join(output_dir, relative_path)
                if not os.path.exists(output_subdir):
                    os.makedirs(output_subdir)

                print(f"Processing PDF: {pdf_path}")
                processor = PDFProcessor(pdf_path)
                processor.process_pdf()
                processor.convert2txt()
                processor.save_txt_and_table()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDFs and extract text and tables.")
    parser.add_argument("input_dir", type=str, help="Directory containing PDF files.")
    parser.add_argument("output_dir", type=str, help="Directory to save extracted text and tables.")
    args = parser.parse_args()

    process_directory(args.input_dir, args.output_dir)
