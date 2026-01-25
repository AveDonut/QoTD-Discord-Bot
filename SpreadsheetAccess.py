import datetime
import os
import random
import gspread
import asyncio

from dotenv import load_dotenv

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")


async def get_question_of_the_day():
    # opens spreadsheet for read/writing
    gc = gspread.service_account()
    sh = gc.open(SPREADSHEET_NAME).sheet1

    #finds today's date
    today = datetime.datetime.strptime(str(datetime.date.today()), '%Y-%m-%d')
    # checks if a qotd is scheduled today
    chosen_question = await spreadsheet_scheduled(sh, today)

    # if no scheduled qotd, pulls from unscheduled pool
    if chosen_question == "null":
       chosen_question = await spreadsheet_unscheduled(sh)

    if chosen_question != "null":
        await spreadsheet_append_column_e(sh, today, chosen_question)
        chosen_question = chosen_question.value

    # quickly grabs numbers to post in qotd
    task1 = get_question_num(sh)
    task2 = get_questions_remaining(sh)

    question_num = await task1
    questions_remaining = await task2

    return str(chosen_question), question_num, questions_remaining


async def spreadsheet_scheduled(sh, today):
    first_blank_in_C = sh.find('',in_column=3)
    scheduled_dates = []

    # grabs all scheduled dates into a list
    if first_blank_in_C != None:
        scheduled_dates = sh.range(f'C2:C{first_blank_in_C.row - 1}')
    else:
        scheduled_dates = sh.range("C2:C{}".format(sh.row_count))
        for i in range(len(scheduled_dates)):
            if scheduled_dates[i].value == '':
                scheduled_dates = scheduled_dates[:i]
                break
        
    for date in scheduled_dates:
        try:
            stripped_date = datetime.datetime.strptime(date.value, '%m/%d/%Y')
            if today == stripped_date:
                print(f"match at {date.address}")

                chosen_question = sh.acell(f'B{date.address[1:]}')
                
                # removes selected question from columns B/C
                copy_range = "B0:C0"
                copy_range = "B" + str(chosen_question.row + 1) + ":C" + str(scheduled_dates[-1].row)

                sh.copy_range(copy_range, chosen_question.address)
                sh.update_acell(scheduled_dates[-1].address, '')
                sh.update_acell(f'B{scheduled_dates[-1].address[1:]}', '')
                
                return chosen_question
        except:
            print(f"a non-date has been found at cell {date.address}")  
        
    return "null"


async def spreadsheet_unscheduled(sh):
    # grabs all unscheduled questions into a list
    first_blank_in_A = sh.find('',in_column=1)
    first_column = []

    if first_blank_in_A != None:

        if first_blank_in_A.address == "A2":
            return "null"
    
        first_column = sh.range(f'A2:A{first_blank_in_A.row - 1}')
    else:
        first_column = sh.range("A2:A{}".format(sh.row_count))
        for i in range(len(first_column)):
            if first_column[i].value == '':
                first_column = first_column[:i]
                break

    # selects random question from column A
    random_question = random.randint(0, len(first_column) - 1)
    chosen_question = first_column[random_question]

    # removes selected question from column A
    copy_range = "A0:A0"
    copy_range = "A" + str(chosen_question.row + 1) + ":A" + str(first_column[-1].row)

    sh.copy_range(copy_range, chosen_question.address)
    sh.update_acell(first_column[-1].address, '')


    return chosen_question


async def spreadsheet_append_column_e(sh, today, chosen_question):

    cell_to_print = sh.find('',in_column=5)
    if cell_to_print == None:
        # appends new row then locates it
        sh.append_row(['','','', '','dummy append'])
        cell_to_print = sh.find('dummy append', in_column=5)

    # writes todays date in the first blank cell of Column E
    sh.update_acell(cell_to_print.address, str(today))
    sh.format(cell_to_print.address, {"numberFormat":{"type":"DATE"}})

    # writes qustion posted in cell left of the date cell
    sh.update_cell(cell_to_print.row, cell_to_print.col - 1, chosen_question.value)

    return


async def get_question_num(sh):
    first_blank_in_E = sh.find('',in_column=5)
    e_column = []

    if first_blank_in_E != None:

        if first_blank_in_E.address == "E2":
            return 1
        
        e_column = sh.range(f'E2:E{first_blank_in_E.row - 1}')
    else:        
        e_column = sh.range("E2:E{}".format(sh.row_count))
        for i in range(len(e_column)):
            if e_column[i].value == '':
                e_column = e_column[:i]
                break

    return len(e_column) + 1


async def get_questions_remaining(sh):
    # grabs all unscheduled questions into a list
    first_blank_in_A = sh.find('',in_column=1)
    first_column = []

    if first_blank_in_A != None:

        if first_blank_in_A.address == "A2":
            return "null"
    
        first_column = sh.range(f'A2:A{first_blank_in_A.row - 1}')
    else:
        first_column = sh.range("A2:A{}".format(sh.row_count))
        for i in range(len(first_column)):
            if first_column[i].value == '':
                first_column = first_column[:i]
                break
    
    return len(first_column)


async def add_unscheduled_question(new_question):
    # opens spreadsheet for read/writing
    gc = gspread.service_account()
    sh = gc.open(SPREADSHEET_NAME).sheet1


    cell_to_print = sh.find('',in_column=1)
    if cell_to_print == None:
        # appends new row then locates it
        sh.append_row(['dummy append'])
        cell_to_print = sh.find('dummy append', in_column=1)
    
    sh.update_acell(cell_to_print.address, new_question)


if __name__ == '__main__':
    print(asyncio.run(get_question_of_the_day()))
    