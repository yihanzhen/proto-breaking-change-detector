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

import unittest
from test.tools.mock_resources import (
    make_file_options_resource_definition,
    make_message_options_resource_definition,
)
from test.tools.mock_descriptors import (
    make_service,
    make_method,
    make_file_set,
    make_file_pb2,
    make_message,
    make_field,
    make_enum,
)
from src.comparator.file_set_comparator import FileSetComparator
from src.findings.finding_container import FindingContainer
from google.protobuf import descriptor_pb2
from google.api import resource_pb2


class FileSetComparatorTest(unittest.TestCase):
    def setUp(self):
        self.finding_container = FindingContainer()

    def test_service_removal(self):
        file_set = make_file_set(
            files=[
                make_file_pb2(
                    services=[make_service()],
                )
            ]
        )
        FileSetComparator(
            file_set,
            make_file_set(),
            self.finding_container,
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MAJOR")

    def test_service_addition(self):
        file_set = make_file_set(
            files=[
                make_file_pb2(
                    services=[make_service()],
                )
            ]
        )
        FileSetComparator(
            make_file_set(),
            file_set,
            self.finding_container,
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.category.name, "SERVICE_ADDITION")
        self.assertEqual(finding.change_type.name, "MINOR")

    def test_service_change(self):
        input_message = make_message(name="request", full_name=".example.v1.request")
        output_message = make_message(name="response", full_name=".example.v1.response")
        service_original = make_service(
            methods=[
                make_method(
                    name="DoThing",
                    input_message=input_message,
                    output_message=output_message,
                )
            ]
        )
        service_update = make_service()
        FileSetComparator(
            make_file_set(
                files=[
                    make_file_pb2(
                        services=[service_original],
                        messages=[input_message, output_message],
                    )
                ]
            ),
            make_file_set(files=[make_file_pb2(services=[service_update])]),
            self.finding_container,
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.category.name, "METHOD_REMOVAL")
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.location.proto_file_name, "my_proto.proto")

    def test_message_change_breaking(self):
        message_original = make_message(
            fields=(make_field(name="field_one", number=1),)
        )
        message_update = make_message(fields=(make_field(name="field_two", number=1),))
        FileSetComparator(
            make_file_set(files=[make_file_pb2(messages=[message_original])]),
            make_file_set(files=[make_file_pb2(messages=[message_update])]),
            self.finding_container,
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.category.name, "FIELD_NAME_CHANGE")
        self.assertEqual(finding.location.proto_file_name, "my_proto.proto")

    def test_message_in_dependency_change_breaking(self):
        # Message "dep_message" is imported from dep.proto and referenced as a field type.
        field_type_original = make_message(
            name="dep_message",
            proto_file_name="dep.proto",
        )
        message_original = make_message(
            fields=[make_field(type_name=".test.import.dep_message")],
        )
        # Message "test_message" is defined in my_proto.proto referenced as a field type.
        field_type_update = make_message(
            name="test_message",
        )
        message_update = make_message(fields=[make_field(type_name="test_message")])
        FileSetComparator(
            make_file_set(
                files=[
                    make_file_pb2(
                        name="orignal.proto",
                        messages=[message_original],
                        dependency="test/import/dep.proto",
                        package="example.v1",
                    ),
                    make_file_pb2(
                        name="dep.proto",
                        messages=[field_type_original],
                        package="test.import",
                    ),
                ]
            ),
            make_file_set(
                files=[
                    make_file_pb2(
                        name="update.proto",
                        messages=[field_type_update, message_update],
                        package="example.v1beta1",
                    )
                ]
            ),
            self.finding_container,
        ).compare()
        # The breaking change should be in field level, instead of message removal,
        # since the message is imported from dependency file.
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.category.name, "FIELD_TYPE_CHANGE")
        self.assertEqual(finding.location.proto_file_name, "update.proto")

    def test_enum_change(self):
        enum_original = make_enum(
            name="Irrelevant",
            values=(
                ("RED", 1),
                ("GREEN", 2),
                ("BLUE", 3),
            ),
        )
        enum_update = make_enum(
            name="Irrelevant",
            values=(
                ("RED", 1),
                ("GREEN", 2),
            ),
        )
        FileSetComparator(
            make_file_set(files=[make_file_pb2(enums=[enum_original])]),
            make_file_set(files=[make_file_pb2(enums=[enum_update])]),
            self.finding_container,
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.category.name, "ENUM_VALUE_REMOVAL")
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.location.proto_file_name, "my_proto.proto")

    def test_enum_in_dependency_change_breaking(self):
        # Enum "dep_message" is imported from dep.proto and referenced as a field type.
        field_type_original = make_enum(
            name="dep_enum",
            proto_file_name="dep.proto",
        )
        message_original = make_message(
            fields=[make_field(type_name=".test.import.dep_enum")],
        )
        # Message "test_enum" is defined in update.proto referenced as a field type.
        field_type_update = make_enum(
            name="test_enum",
        )
        message_update = make_message(fields=[make_field(type_name="test_enum")])
        FileSetComparator(
            make_file_set(
                files=[
                    make_file_pb2(
                        name="orignal.proto",
                        messages=[message_original],
                        dependency="test/import/dep.proto",
                        package="example.v1",
                    ),
                    make_file_pb2(
                        name="dep.proto",
                        enums=[field_type_original],
                        package="test.import",
                    ),
                ]
            ),
            make_file_set(
                files=[
                    make_file_pb2(
                        name="update.proto",
                        messages=[message_update],
                        enums=[field_type_update],
                        package="example.v1beta1",
                    )
                ]
            ),
            self.finding_container,
        ).compare()
        # The breaking change should be in field level, instead of message removal,
        # since the message is imported from dependency file.
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.category.name, "FIELD_TYPE_CHANGE")
        self.assertEqual(finding.location.proto_file_name, "update.proto")

    def test_resources_existing_pattern_change(self):
        options_original = make_file_options_resource_definition(
            resource_type=".example.v1.Bar", resource_patterns=["foo/{foo}/bar/{bar}"]
        )
        file_pb2 = make_file_pb2(
            name="foo.proto", package=".example.v1", options=options_original
        )
        file_set_original = make_file_set(files=[file_pb2])
        options_update = make_file_options_resource_definition(
            resource_type=".example.v1.Bar", resource_patterns=["foo/{foo}/bar/"]
        )
        file_pb2 = make_file_pb2(
            name="foo.proto", package=".example.v1", options=options_update
        )
        file_set_update = make_file_set(files=[file_pb2])

        FileSetComparator(
            file_set_original, file_set_update, self.finding_container
        ).compare()
        finding = next(
            f
            for f in self.finding_container.get_all_findings()
            if f.change_type.name == "MAJOR"
        )
        self.assertEqual(finding.category.name, "RESOURCE_PATTERN_REMOVAL")
        self.assertEqual(
            finding.location.proto_file_name,
            "foo.proto",
        )

    def test_resources_existing_pattern_removal(self):
        options_original = make_file_options_resource_definition(
            resource_type=".example.v1.Bar",
            resource_patterns=["bar/{bar}", "foo/{foo}/bar"],
        )
        file_pb2 = make_file_pb2(
            name="foo.proto", package=".example.v1", options=options_original
        )
        file_set_original = make_file_set(files=[file_pb2])

        options_update = make_file_options_resource_definition(
            resource_type=".example.v1.Bar", resource_patterns=["bar/{bar}"]
        )
        file_pb2 = make_file_pb2(
            name="foo.proto", package=".example.v1", options=options_update
        )
        file_set_update = make_file_set(files=[file_pb2])

        FileSetComparator(
            file_set_original, file_set_update, self.finding_container
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MAJOR")
        self.assertEqual(finding.category.name, "RESOURCE_PATTERN_REMOVAL")
        self.assertEqual(
            finding.location.proto_file_name,
            "foo.proto",
        )

    def test_resources_addition(self):
        file_set_original = make_file_set(
            files=[make_file_pb2(name="foo.proto", package=".example.v1")]
        )

        options_update = make_file_options_resource_definition(
            resource_type=".example.v1.Bar", resource_patterns=["foo/{foo}/bar/{bar}"]
        )
        file_pb2 = make_file_pb2(
            name="foo.proto", package=".example.v1", options=options_update
        )
        file_set_update = make_file_set(files=[file_pb2])
        FileSetComparator(
            file_set_original, file_set_update, self.finding_container
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.change_type.name, "MINOR")
        self.assertEqual(
            finding.category.name,
            "RESOURCE_DEFINITION_ADDITION",
        )
        self.assertEqual(
            finding.location.proto_file_name,
            "foo.proto",
        )

    def test_resources_removal(self):
        # Create message with resource options.
        message_options = make_message_options_resource_definition(
            resource_type="example.v1/Bar",
            resource_patterns=["user/{user}", "user/{user}/bar/"],
        )
        message = make_message("Test", options=message_options)
        # Original file set with one resource defined at message level.
        file_set_original = make_file_set(
            files=[
                make_file_pb2(
                    name="bar.proto", package=".example.v1", messages=[message]
                )
            ]
        )
        # Update file set without any resources.
        file_set_update = make_file_set(
            files=[make_file_pb2(name="foo.proto", package=".example.v1")]
        )
        FileSetComparator(
            file_set_original, file_set_update, self.finding_container
        ).compare()
        file_resource_removal = next(
            f
            for f in self.finding_container.get_all_findings()
            if f.category.name == "RESOURCE_DEFINITION_REMOVAL"
        )
        self.assertEqual(
            file_resource_removal.location.proto_file_name,
            "bar.proto",
        )

    def test_java_outer_classname_removal(self):
        option1 = descriptor_pb2.FileOptions()
        option1.java_outer_classname = "Foo"
        file1 = make_file_pb2(
            name="fil1.proto",
            package="example.v1",
            options=option1,
        )
        option2 = descriptor_pb2.FileOptions()
        option2.java_outer_classname = "Bar"
        file2 = make_file_pb2(
            name="fil2.proto",
            package="example.v1",
            options=option2,
        )
        file_set_original = make_file_set(files=[file1, file2])
        option3 = descriptor_pb2.FileOptions()
        option3.java_outer_classname = "Bar"
        file3 = make_file_pb2(
            name="file3.proto", package="example.v1beta", options=option3
        )
        file_set_update = make_file_set(files=[file3])
        FileSetComparator(
            file_set_original, file_set_update, self.finding_container
        ).compare()
        finding = self.finding_container.get_all_findings()[0]
        self.assertEqual(finding.category.name, "PACKAGING_OPTION_REMOVAL")
        self.assertEqual(finding.change_type.name, "MAJOR")

    def test_packaging_options_change(self):
        file_options_original = descriptor_pb2.FileOptions()
        file_options_original.php_namespace = "Google\\Cloud\\Service\\V1"
        file_options_original.csharp_namespace = "Google.Cloud.Service.V1"
        file_options_original.java_outer_classname = "ServiceProto"
        file_original = make_file_pb2(
            name="original.proto",
            package="google.cloud.service.v1",
            options=file_options_original,
        )

        file_options_update = descriptor_pb2.FileOptions()
        # Breaking since version should be updated to `v1alpha`
        file_options_update.php_namespace = "Google\\Cloud\\Service\\V1beta"
        # No breaking change
        file_options_update.csharp_namespace = "Google.Cloud.Service.V1alpha"
        file_options_update.java_outer_classname = "ServiceUpdateProto"
        file_update = make_file_pb2(
            name="update.proto",
            package="google.cloud.service.v1alpha",
            options=file_options_update,
        )

        FileSetComparator(
            make_file_set(files=[file_original]),
            make_file_set(files=[file_update]),
            self.finding_container,
        ).compare()
        java_classname_option_removal = next(
            f
            for f in self.finding_container.get_all_findings()
            if f.category.name == "PACKAGING_OPTION_REMOVAL"
            and f.subject == "java_outer_classname"
        )
        php_namespace_option_removal = next(
            f
            for f in self.finding_container.get_all_findings()
            if f.category.name == "PACKAGING_OPTION_REMOVAL"
            and f.subject == "php_namespace"
        )
        self.assertTrue(java_classname_option_removal)
        self.assertTrue(php_namespace_option_removal)

    def test_packaging_options_version_update(self):
        file_options_original = descriptor_pb2.FileOptions()
        file_options_original.java_outer_classname = "ServiceProto"
        file_options_original.java_package = "com.google.cloud.service.v1"
        file_options_original.csharp_namespace = "Google.Cloud.Service.V1"
        file_options_original.php_namespace = "Google\\Cloud\\Service\\V1"
        file_options_original.ruby_package = "Google::Cloud::Service::V1"
        file_original = make_file_pb2(
            name="original.proto",
            package="google.cloud.service.v1",
            options=file_options_original,
        )

        file_options_update = descriptor_pb2.FileOptions()
        file_options_update.java_outer_classname = "ServiceProto"
        file_options_update.java_package = "com.google.cloud.service.v1alpha"
        file_options_update.csharp_namespace = "Google.Cloud.Service.V1alpha"
        file_options_update.php_namespace = "Google\\Cloud\\Service\\V1alpha"
        file_options_update.ruby_package = "Google::Cloud::Service::V1alpha"
        file_update = make_file_pb2(
            name="update.proto",
            package="google.cloud.service.v1alpha",
            options=file_options_update,
        )

        FileSetComparator(
            make_file_set(files=[file_original]),
            make_file_set(files=[file_update]),
            self.finding_container,
        ).compare()
        self.assertEqual(self.finding_container.get_all_findings(), [])


if __name__ == "__main__":
    unittest.main()
