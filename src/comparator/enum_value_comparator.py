# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from src.findings.finding_container import FindingContainer
from src.findings.finding_category import FindingCategory, ChangeType
from src.comparator.wrappers import EnumValue


class EnumValueComparator:
    def __init__(
        self,
        enum_value_original: EnumValue,
        enum_value_update: EnumValue,
        finding_container: FindingContainer,
        context: str,
    ):
        self.enum_value_original = enum_value_original
        self.enum_value_update = enum_value_update
        self.finding_container = finding_container
        self.context = context

    def compare(self):
        # 1. If the original EnumValue is None, then a new EnumValue is added.
        if self.enum_value_original is None:
            self.finding_container.add_finding(
                category=FindingCategory.ENUM_VALUE_ADDITION,
                proto_file_name=self.enum_value_update.proto_file_name,
                source_code_line=self.enum_value_update.source_code_line,
                subject=self.enum_value_update.name,
                context=self.context,
                change_type=ChangeType.MINOR,
            )
        # 2. If the updated EnumValue is None, then the original EnumValue is removed.
        elif self.enum_value_update is None:
            self.finding_container.add_finding(
                category=FindingCategory.ENUM_VALUE_REMOVAL,
                proto_file_name=self.enum_value_original.proto_file_name,
                source_code_line=self.enum_value_original.source_code_line,
                subject=self.enum_value_original.name,
                context=self.context,
                change_type=ChangeType.MAJOR,
            )
        # 3. If both EnumValueDescriptors are existing, check if the name is identical.
        elif self.enum_value_original.name != self.enum_value_update.name:
            self.finding_container.add_finding(
                category=FindingCategory.ENUM_VALUE_NAME_CHANGE,
                proto_file_name=self.enum_value_update.proto_file_name,
                source_code_line=self.enum_value_update.source_code_line,
                subject=self.enum_value_update.name,
                oldsubject=self.enum_value_original.name,
                context=self.context,
                change_type=ChangeType.MAJOR,
                extra_info=self.enum_value_update.nested_path,
            )
