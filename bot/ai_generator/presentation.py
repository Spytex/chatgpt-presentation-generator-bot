import os
import random
import re
import string
import io

import openai
import config
from pptx import Presentation

try:
    from image_scrapper import downloader
except ImportError:
    from .image_scrapper import downloader


openai.api_key = config.openai_api_key

OPENAI_COMPLETION_OPTIONS = {
    "temperature": 0,
    "max_tokens": 1000,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0
}

bad_coding_practice = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in
                              range(16))


async def refresh_bad_coding_practice():
    global bad_coding_practice
    bad_coding_practice = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
                                  for _ in range(16))
    return


async def generate_ppt_prompt(language, emotion_type, slide_length, topic):
    message = f"""Create an {language} language outline for a {emotion_type} slideshow presentation on the topic of {topic} which is {slide_length} slides 
        long. 

        You are allowed to use the following slide types:

        Slide types:
        Title Slide - (Title, Subtitle)
        Content Slide - (Title, Content)
        Image Slide - (Title, Content, Image)
        Thanks Slide - (Title)

        Put this tag before the Title Slide: [L_TS]
        Put this tag before the Content Slide: [L_CS]
        Put this tag before the Image Slide: [L_IS]
        Put this tag before the Thanks Slide: [L_THS]

        Put "[SLIDEBREAK]" after each slide 

        For example:
        [L_TS]
        [TITLE]Mental Health[/TITLE]

        [SLIDEBREAK]

        [L_CS] 
        [TITLE]Mental Health Definition[/TITLE]
        [CONTENT]
        1. Definition: A person’s condition with regard to their psychological and emotional well-being
        2. Can impact one's physical health
        3. Stigmatized too often.
        [/CONTENT]

        [SLIDEBREAK]

        Put this tag before the Title: [TITLE]
        Put this tag after the Title: [/TITLE]
        Put this tag before the Subitle: [SUBTITLE]
        Put this tag after the Subtitle: [/SUBTITLE]
        Put this tag before the Content: [CONTENT]
        Put this tag after the Content: [/CONTENT]
        Put this tag before the Image: [IMAGE]
        Put this tag after the Image: [/IMAGE]

        Elaborate on the Content, provide as much information as possible.
        You put a [/CONTENT] at the end of the Content.
        Do not reply as if you are talking about the slideshow itself. (ex. "Include pictures here about...")
        Do not include any special characters (?, !, ., :, ) in the Title.
        Do not include any additional information in your response and stick to the format."""

    return message


async def process_ppt_prompt(message):
    answer = None
    while answer is None:
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": message}
                ],
                **OPENAI_COMPLETION_OPTIONS
            )
            answer = response['choices'][0]['message']['content']
            n_used_tokens = response.usage.total_tokens
        except openai.error.InvalidRequestError as e:  # too many tokens
            raise ValueError("Too many tokens to make completion") from e
        except openai.error.RateLimitError as e:
            raise OverflowError("That model is currently overloaded with other requests.") from e
        except openai.error.APIError as e:
            raise RuntimeError("HTTP code 502 from API") from e
    return answer, n_used_tokens


async def generate_ppt(answer, template):
    template = os.path.join("bot", "ai_generator", "presentation_templates", f"{template}.pptx")
    root = Presentation(template)

    # """ Ref for slide types:
    # 0 -> title and subtitle
    # 1 -> title and content
    # 2 -> section header
    # 3 -> two content
    # 4 -> Comparison
    # 5 -> Title only
    # 6 -> Blank
    # 7 -> Content with caption
    # 8 -> Pic with caption
    # """

    def delete_all_slides():
        for i in range(len(root.slides) - 1, -1, -1):
            r_id = root.slides._sldIdLst[i].rId
            root.part.drop_rel(r_id)
            del root.slides._sldIdLst[i]

    def create_title_slide(title, subtitle):
        layout = root.slide_layouts[0]
        slide = root.slides.add_slide(layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = subtitle

    def create_section_header_slide(title):
        layout = root.slide_layouts[2]
        slide = root.slides.add_slide(layout)
        slide.shapes.title.text = title

    def create_title_and_content_slide(title, content):
        layout = root.slide_layouts[1]
        slide = root.slides.add_slide(layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = content

    def create_title_and_content_and_image_slide(title, content, image_query):
        layout = root.slide_layouts[8]
        slide = root.slides.add_slide(layout)
        slide.shapes.title.text = title
        slide.placeholders[2].text = content

        refresh_bad_coding_practice()
        image_data = downloader.download(image_query, limit=1, adult_filter_off=True, timeout=15,
                                         filter="+filterui:aspect-wide+filterui:imagesize-wallpaper")
        slide.placeholders[1].insert_picture(io.BytesIO(image_data))
        # slide.shapes.add_picture(io.BytesIO(image_data), slide.placeholders[1].left, slide.placeholders[1].top,
        #                          slide.placeholders[1].width, slide.placeholders[1].height)

    def find_text_in_between_tags(text, start_tag, end_tag):
        start_pos = text.find(start_tag)
        end_pos = text.find(end_tag)
        result = []
        while start_pos > -1 and end_pos > -1:
            text_between_tags = text[start_pos + len(start_tag):end_pos]
            result.append(text_between_tags)
            start_pos = text.find(start_tag, end_pos + len(end_tag))
            end_pos = text.find(end_tag, start_pos)
        res1 = "".join(result)
        res2 = re.sub(r"\[IMAGE\].*?\[/IMAGE\]", '', res1)
        if len(result) > 0:
            return res2
        else:
            return ""

    def search_for_slide_type(text):
        tags = ["[L_TS]", "[L_CS]", "[L_IS]", "[L_THS]"]
        found_text = next((s for s in tags if s in text), None)
        return found_text

    def parse_response(reply):
        list_of_slides = reply.split("[SLIDEBREAK]")
        for slide in list_of_slides:
            slide_type = search_for_slide_type(slide)
            if slide_type == "[L_TS]":
                create_title_slide(find_text_in_between_tags(str(slide), "[TITLE]", "[/TITLE]"),
                                   find_text_in_between_tags(str(slide), "[SUBTITLE]", "[/SUBTITLE]"))
            elif slide_type == "[L_CS]":
                create_title_and_content_slide("".join(find_text_in_between_tags(str(slide), "[TITLE]", "[/TITLE]")),
                                               "".join(find_text_in_between_tags(str(slide), "[CONTENT]",
                                                                                 "[/CONTENT]")))
            elif slide_type == "[L_IS]":
                create_title_and_content_and_image_slide("".join(find_text_in_between_tags(str(slide), "[TITLE]",
                                                                                           "[/TITLE]")),
                                                         "".join(find_text_in_between_tags(str(slide), "[CONTENT]",
                                                                                           "[/CONTENT]")),
                                                         "".join(find_text_in_between_tags(str(slide), "[IMAGE]",
                                                                                           "[/IMAGE]")))
            elif slide_type == "[L_THS]":
                create_section_header_slide("".join(find_text_in_between_tags(str(slide), "[TITLE]", "[/TITLE]")))

    def find_title():
        return root.slides[0].shapes.title.text

    delete_all_slides()
    parse_response(answer)
    buffer = io.BytesIO()
    root.save(buffer)
    pptx_bytes = buffer.getvalue()
    pptx_title = f"{find_title()}.pptx"
    print("done")

    return pptx_bytes, pptx_title
